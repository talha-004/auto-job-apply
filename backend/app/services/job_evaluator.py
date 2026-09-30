"""
Central Job Intelligence & Evaluation Engine Coordinator.
Coordinates MatchScorer, JobQualityScorer, contact extraction, and hard disqualification rules.
"""

import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Union

from app.models.job import (
    ResumeProfile,
    SearchConfig,
    DiscoveredJob,
    JobEvaluationResult,
)
from app.services.match_scorer import match_scorer, MatchResult
from app.services.job_quality_scorer import job_quality_scorer, JobQualityResult
from app.platforms.naukri_helpers import extract_job_contacts, JobContact


def parse_salary_text(salary_text: str) -> Dict[str, Any]:
    """
    Parses compensation text into structured min/max values, currency, and period.
    Handles:
      - "12 - 18 LPA", "15 Lacs P.A.", "₹ 12,00,000 - 18,00,000 P.A."
      - "$120,000 - $160,000 a year", "$120k - $160k"
      - "$50 - $70 an hour", "$60/hr"
      - "₹40,000 - ₹60,000 a month"
    """
    if not salary_text or not isinstance(salary_text, str):
        return {"min_salary": None, "max_salary": None, "currency": None, "period": None, "raw": ""}

    text = salary_text.strip()
    result: Dict[str, Any] = {
        "min_salary": None,
        "max_salary": None,
        "currency": "INR",
        "period": "LPA",
        "raw": text
    }

    # Detect currency
    if "$" in text or "usd" in text.lower():
        result["currency"] = "USD"
        result["period"] = "ANNUAL"
    elif "€" in text or "eur" in text.lower():
        result["currency"] = "EUR"
        result["period"] = "ANNUAL"
    elif "£" in text or "gbp" in text.lower():
        result["currency"] = "GBP"
        result["period"] = "ANNUAL"
    elif any(k in text.lower() for k in ["₹", "inr", "lpa", "lac", "lakh"]):
        result["currency"] = "INR"
        result["period"] = "LPA"

    # Detect frequency
    if any(k in text.lower() for k in ["/hr", "an hour", "hourly", "per hour"]):
        result["period"] = "HOURLY"
    elif any(k in text.lower() for k in ["/mo", "a month", "monthly", "per month"]):
        result["period"] = "MONTHLY"

    # 1. LPA / Lacs pattern (e.g. "12 - 18 LPA", "15 Lacs P.A.")
    lpa_match = re.search(r'[\$€£₹]?\s*(\d+(?:\.\d+)?)\s*(?:-|to)?\s*[\$€£₹]?\s*(\d+(?:\.\d+)?)?\s*(?:lpa|lacs?|lakhs?)', text, re.IGNORECASE)
    if lpa_match:
        v1 = float(lpa_match.group(1))
        v2 = float(lpa_match.group(2)) if lpa_match.group(2) else v1
        result["min_salary"] = min(v1, v2)
        result["max_salary"] = max(v1, v2)
        result["period"] = "LPA"
        result["currency"] = "INR"
        return result

    # 2. "120k - 160k" notation
    k_range = re.search(r'[\$€£₹]?\s*(\d+(?:\.\d+)?)\s*k?\s*(?:-|to)\s*[\$€£₹]?\s*(\d+(?:\.\d+)?)\s*k', text, re.IGNORECASE)
    if k_range:
        v1 = float(k_range.group(1)) * 1000.0
        v2 = float(k_range.group(2)) * 1000.0
        result["min_salary"] = min(v1, v2)
        result["max_salary"] = max(v1, v2)
        return result

    single_k = re.search(r'[\$€£₹]?\s*(\d+(?:\.\d+)?)\s*k', text, re.IGNORECASE)
    if single_k:
        val = float(single_k.group(1)) * 1000.0
        result["min_salary"] = val
        result["max_salary"] = val
        return result

    # 3. Numeric values with commas (e.g. "1,200,000 - 1,800,000" or "12,00,000")
    nums = re.findall(r'(\d+(?:,\d+)*(?:\.\d+)?)', text)
    cleaned = []
    for n in nums:
        try:
            val = float(n.replace(',', ''))
            if val > 0:
                cleaned.append(val)
        except ValueError:
            pass

    if cleaned:
        min_v = cleaned[0]
        max_v = cleaned[1] if len(cleaned) > 1 else min_v
        if result["currency"] == "INR" and min_v >= 100000.0:
            min_v = round(min_v / 100000.0, 2)
            max_v = round(max_v / 100000.0, 2)
            result["period"] = "LPA"
        result["min_salary"] = min(min_v, max_v)
        result["max_salary"] = max(min_v, max_v)

    return result


class JobEvaluator:
    """
    Central evaluation coordinator combining:
      1. Deterministic MatchScorer (60/20/10/10 math)
      2. JobQualityScorer (transparency & spam/risk detection)
      3. Contact Extractor (direct recruiter/HR emails)
      4. Hard Disqualification Rules (blacklists, compensation/location sanity, technology mismatches)
    """

    CRITICAL_RISK_FLAGS = {"DEPOSIT_REQUIRED", "TRAINING_PURCHASE"}

    def evaluate_job(
        self,
        job: Union[DiscoveredJob, Dict[str, Any]],
        profile: ResumeProfile,
        config: Optional[SearchConfig] = None
    ) -> JobEvaluationResult:
        if config is None:
            config = SearchConfig()

        # Extract normalized attributes
        if isinstance(job, DiscoveredJob):
            job_id = job.job_id
            title = job.title
            company = job.company
            location = job.location
            jd_text = job.description
            is_remote = job.is_remote
            platform = job.platform
            raw_metadata = job.raw_metadata or {}
        else:
            job_id = str(job.get("job_id") or job.get("id") or "UNKNOWN")
            title = str(job.get("title") or job.get("job_title") or "")
            company = str(job.get("company") or "")
            location = str(job.get("location") or "")
            jd_text = str(job.get("description") or job.get("jd_text") or "")
            is_remote = bool(job.get("is_remote", False))
            platform = str(job.get("platform") or "unknown")
            raw_metadata = job.get("raw_metadata") or {}

        disqualification_reasons: List[str] = []
        is_hard_disqualified = False

        # 1. Hard Disqualification: Excluded Companies / Blacklist
        if config.excluded_companies:
            comp_lower = company.lower()
            for bad_comp in config.excluded_companies:
                if bad_comp and bad_comp.lower() in comp_lower:
                    is_hard_disqualified = True
                    disqualification_reasons.append(f"Company '{company}' matches excluded company filter '{bad_comp}'.")

        # 2. Hard Disqualification: Remote Requirement
        title_loc_text = f"{title.lower()} {location.lower()} {jd_text.lower()[:300]}"
        is_job_remote = is_remote or "remote" in title_loc_text or "work from home" in title_loc_text or "wfh" in title_loc_text
        if config.require_remote and not is_job_remote:
            is_hard_disqualified = True
            disqualification_reasons.append("Job is not remote, but search configuration requires remote positions.")

        # 3. Location Sanity Gating: Prohibited & Allowed Locations
        if config.prohibited_locations:
            loc_lower = location.lower()
            for proh in config.prohibited_locations:
                if proh and proh.strip().lower() in loc_lower:
                    is_hard_disqualified = True
                    disqualification_reasons.append(
                        f"Location '{location}' is in prohibited locations filter ('{proh}')."
                    )

        if config.allowed_locations and not is_job_remote:
            loc_lower = location.lower()
            matched_allowed = any(allowed.strip().lower() in loc_lower for allowed in config.allowed_locations if allowed.strip())
            if not matched_allowed:
                if config.strict_location_enforcement:
                    is_hard_disqualified = True
                    disqualification_reasons.append(
                        f"On-site location '{location}' is outside permitted locations: {config.allowed_locations}."
                    )
                else:
                    disqualification_reasons.append(
                        f"Location notice: Location '{location}' is outside allowed locations list ({config.allowed_locations})."
                    )

        # 4. Strict Compensation Sanity Gating
        salary_source = (
            raw_metadata.get("salary") or 
            raw_metadata.get("salary_raw") or 
            (f"{job.salary_min} - {job.salary_max}" if isinstance(job, DiscoveredJob) and job.salary_min else "") or
            ""
        )
        parsed_salary = parse_salary_text(str(salary_source))
        if config.min_salary is not None and parsed_salary.get("max_salary") is not None:
            offered_max = parsed_salary["max_salary"]
            target_curr = (config.salary_currency or "INR").upper()
            parsed_curr = (parsed_salary.get("currency") or "INR").upper()
            if target_curr == parsed_curr:
                if offered_max < config.min_salary:
                    reason = (
                        f"Offered compensation (max {offered_max} {parsed_salary.get('period', '')}) "
                        f"is below minimum expected floor ({config.min_salary} {target_curr})."
                    )
                    if config.strict_salary_enforcement:
                        is_hard_disqualified = True
                        disqualification_reasons.append(reason)
                    else:
                        disqualification_reasons.append(f"Compensation warning: {reason}")

        # 3. Deterministic Match Scoring (60/20/10/10)
        match_res: MatchResult = match_scorer.score_job(
            job_title=title,
            jd_text=jd_text,
            profile=profile,
            min_threshold=config.min_match_score,
            excluded_keywords=config.excluded_keywords,
            max_experience_gap=config.max_experience_gap
        )

        if not match_res.is_eligible:
            for r in match_res.reasons:
                if any(k in r for k in ["detected in job posting", "exceeds candidate", "Core technology"]):
                    is_hard_disqualified = True
                    disqualification_reasons.append(r)

        # Enforce match gating if mode is 'enforce'
        if config.match_gating_mode == "enforce" and match_res.score < config.min_match_score:
            is_hard_disqualified = True
            disqualification_reasons.append(
                f"Match score ({match_res.score}%) is below required minimum threshold ({config.min_match_score}%)."
            )

        # 4. Contact Extraction
        recruiter_text = raw_metadata.get("recruiter_name") or raw_metadata.get("recruiter_text") or ""
        contacts_objs: List[JobContact] = extract_job_contacts(jd_text, recruiter_text)
        contacts_dicts = [c.model_dump() for c in contacts_objs]
        has_contact = len(contacts_objs) > 0
        hr_email = contacts_objs[0].email if contacts_objs else None
        recruiter_name = contacts_objs[0].name if (contacts_objs and contacts_objs[0].name) else None

        # 5. Job Quality and Risk Scoring
        quality_res: JobQualityResult = job_quality_scorer.evaluate(
            job_title=title,
            company=company,
            jd_text=jd_text,
            match_score=match_res.score,
            has_contact=has_contact,
            is_quick_apply=config.quick_apply_only,
            freshness_days=config.freshness_days,
            location=location,
            contacts=contacts_dicts
        )

        # Check for Critical Risk Flags (Security deposit, scam training)
        critical_flags = set(quality_res.risk_flags).intersection(self.CRITICAL_RISK_FLAGS)
        if critical_flags:
            is_hard_disqualified = True
            for flag in critical_flags:
                evidence = quality_res.risk_evidence.get(flag, "High scam risk pattern detected.")
                disqualification_reasons.append(f"Critical risk flag '{flag}': {evidence}")

        # 6. Overall Eligibility & Suggested Action
        is_eligible = not is_hard_disqualified
        if not is_eligible:
            suggested_action = "SKIP"
        elif "CONFIDENTIAL_UNVERIFIED" in quality_res.risk_flags and match_res.score >= 70:
            suggested_action = "MANUAL_REVIEW"
        elif quality_res.priority_score >= 60:
            suggested_action = "APPLY"
        else:
            suggested_action = "APPLY"

        # Summary line
        status_label = "ELIGIBLE" if is_eligible else "DISQUALIFIED"
        summary = (
            f"[{status_label}] Match: {match_res.score}%, Quality: {quality_res.quality_score}%, "
            f"Priority: {quality_res.priority_score}% -> Action: {suggested_action}"
        )

        return JobEvaluationResult(
            job_id=job_id,
            title=title,
            company=company,
            location=location,
            is_eligible=is_eligible,
            disqualification_reasons=disqualification_reasons,
            match_score=match_res.score,
            matched_skills=match_res.matched_skills,
            missing_skills=match_res.missing_required,
            matched_preferred=match_res.matched_preferred,
            match_reasons=match_res.reasons,
            quality_score=quality_res.quality_score,
            quality_reasons=quality_res.quality_reasons,
            priority_score=quality_res.priority_score,
            priority_reasons=quality_res.priority_reasons,
            risk_flags=quality_res.risk_flags,
            risk_evidence=quality_res.risk_evidence,
            contacts=contacts_dicts,
            hr_email=hr_email,
            recruiter_name=recruiter_name,
            suggested_action=suggested_action,
            evaluation_summary=summary
        )

    def evaluate_batch(
        self,
        jobs: List[Union[DiscoveredJob, Dict[str, Any]]],
        profile: ResumeProfile,
        config: Optional[SearchConfig] = None
    ) -> List[JobEvaluationResult]:
        """Evaluate a batch of jobs sequentially."""
        return [self.evaluate_job(j, profile, config) for j in jobs]

    def filter_and_rank(
        self,
        jobs: List[DiscoveredJob],
        profile: ResumeProfile,
        config: Optional[SearchConfig] = None
    ) -> List[Tuple[DiscoveredJob, JobEvaluationResult]]:
        """
        Evaluate and return only eligible jobs, sorted by:
        1. Priority score descending
        2. Match score descending
        3. Quality score descending
        """
        evaluations = self.evaluate_batch(jobs, profile, config)
        eligible_pairs: List[Tuple[DiscoveredJob, JobEvaluationResult]] = []
        for job_obj, eval_res in zip(jobs, evaluations):
            if eval_res.is_eligible:
                eligible_pairs.append((job_obj, eval_res))

        eligible_pairs.sort(
            key=lambda pair: (pair[1].priority_score, pair[1].match_score, pair[1].quality_score),
            reverse=True
        )
        return eligible_pairs


job_evaluator = JobEvaluator()
