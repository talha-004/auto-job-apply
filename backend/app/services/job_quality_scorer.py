"""
Job Quality and Application Priority Scoring Engine.
Evaluates the transparency, completeness, and legitimacy of a job listing,
detects suspicious listings/risk flags, and derives an explainable Priority Score.
Governed by the rule: Match Score, Job Quality Score, and Risk Flags remain distinct.
"""

import re
from typing import List, Tuple, Optional, Any, Dict
from pydantic import BaseModel, Field


class JobQualityResult(BaseModel):
    quality_score: int = Field(..., ge=0, le=100)
    risk_flags: List[str] = Field(default_factory=list)
    risk_evidence: Dict[str, str] = Field(default_factory=dict)
    quality_reasons: List[str] = Field(default_factory=list)
    priority_score: int = Field(..., ge=0, le=100)
    priority_reasons: List[str] = Field(default_factory=list)


class JobQualityScorer:
    # High-risk suspicious terms that should flag for manual review
    RISK_PATTERNS = {
        "DEPOSIT_REQUIRED": [
            r"security deposit", r"refundable deposit", r"laptop deposit",
            r"deposit required"
        ],
        "TRAINING_PURCHASE": [
            r"mandatory paid training", r"purchase course", r"paid certification required",
            r"purchase training"
        ],
        "CONFIDENTIAL_UNVERIFIED": [
            r"confidential company", r"unnamed client", r"undisclosed startup"
        ]
    }

    # Patterns indicating disclaimers, anti-fraud advice, or negations
    NEGATION_ADVISORY_PATTERNS = [
        r"\b(?:never|not|no|don't|does not|doesn't|without|do not|never ask|never charge|free of cost|no charge)\b",
        r"\b(?:beware|caution|fraud|fraudulent|scam|warning|disclaimer|fake|impostor|imposter)\b",
        r"\b(?:naukri|indeed|linkedin|portal|platform)\s*(?:does not|never|will never|doesn't)\b",
        r"\b(?:avoid paying|never pay|do not pay|report fraudulent|no fee)\b",
    ]

    def evaluate(
        self,
        job_title: str = "",
        company: str = "",
        jd_text: str = "",
        match_score: int = 0,
        has_contact: bool = False,
        is_quick_apply: bool = True,
        freshness_days: Optional[int] = None,
        location: Optional[str] = None,
        contacts: Optional[List[Any]] = None,
        title: Optional[str] = None,
        **kwargs
    ) -> JobQualityResult:
        actual_title = title or job_title
        if contacts and not has_contact:
            has_contact = len(contacts) > 0

        if not jd_text:
            return JobQualityResult(
                quality_score=0,
                risk_flags=["EMPTY_JOB_DESCRIPTION"],
                risk_evidence={"EMPTY_JOB_DESCRIPTION": "Empty job description text."},
                quality_reasons=["Empty job description text."],
                priority_score=0,
                priority_reasons=["Zero quality score due to empty JD."]
            )

        jd_lower = jd_text.lower()
        quality_score = 0
        quality_reasons: List[str] = []
        risk_flags: List[str] = []

        # 1. Disclosed Salary (+15)
        # Check for INR, Lakhs, LPA, $, per annum, or digit ranges
        has_salary = bool(re.search(r"(?:₹|\$|inr|lpa|lakhs?|ctc|\b\d{1,2}\s*-\s*\d{1,2}\s*(?:lpa|lac|lakh))\b", jd_lower))
        if has_salary and "not disclosed" not in jd_lower:
            quality_score += 15
            quality_reasons.append("Disclosed salary / compensation range (+15)")
        else:
            quality_reasons.append("Salary not explicitly disclosed")

        # 2. Clear Experience Range (+15)
        has_exp = bool(re.search(r"\b\d{1,2}\s*(?:-\s*\d{1,2}|\+)?\s*(?:years?|yrs?)\b", jd_lower))
        if has_exp:
            quality_score += 15
            quality_reasons.append("Explicit experience requirements stated (+15)")

        # 3. Key Skills Specified (+20)
        # Check for technical bullet lists or comma separated skills
        tech_tokens = ["python", "java", "javascript", "react", "node", "sql", "api", "aws", "docker", "c++", "golang", "html", "css"]
        found_tokens = [t for t in tech_tokens if re.search(rf"\b{re.escape(t)}\b", jd_lower)]
        if len(found_tokens) >= 3:
            quality_score += 20
            quality_reasons.append(f"Clear technology skill requirements ({len(found_tokens)} detected) (+20)")
        elif len(found_tokens) >= 1:
            quality_score += 10
            quality_reasons.append("Partial technology skill requirements stated (+10)")

        # 4. Company Information (+15)
        if company and company.lower() not in ("company", "tech firm", "client") and len(company) >= 3:
            quality_score += 15
            quality_reasons.append(f"Recognized company entity '{company}' (+15)")

        # 5. Recruiter / Contact Availability (+15)
        if has_contact:
            quality_score += 15
            quality_reasons.append("Recruiter or hiring contact available (+15)")

        # 6. Specific Office Location (+10)
        has_loc = bool(re.search(r"\b(?:bangalore|bengaluru|hyderabad|pune|mumbai|delhi|noida|gurgaon|chennai|remote|hybrid)\b", jd_lower))
        if has_loc:
            quality_score += 10
            quality_reasons.append("Clear work location / mode stated (+10)")

        # 7. JD Completeness & Structure (+10)
        if len(jd_text.strip()) >= 350:
            quality_score += 10
            quality_reasons.append("Thorough job description structure (+10)")

        # 8. Check Candidate Evidence for Risk Flags
        # Splits text into sentences/lines to preserve the exact suspicious snippet
        risk_evidence: Dict[str, str] = {}
        raw_sentences = [s.strip() for s in re.split(r"[\r\n.!?•;]+", jd_text) if len(s.strip()) > 3]

        for sentence in raw_sentences:
            s_lower = sentence.lower()
            is_advisory = any(bool(re.search(pat, s_lower)) for pat in self.NEGATION_ADVISORY_PATTERNS)

            for flag, patterns in self.RISK_PATTERNS.items():
                if flag in risk_flags:
                    continue  # Already flagged and evidence recorded
                
                matched = False
                for p in patterns:
                    if re.search(p, s_lower):
                        matched = True
                        break

                if matched:
                    # Non-financial: flag without checking advisory/negation
                    if flag == "CONFIDENTIAL_UNVERIFIED":
                        risk_flags.append(flag)
                        risk_evidence[flag] = sentence
                    else:
                        # Risk flags (DEPOSIT_REQUIRED, TRAINING_PURCHASE):
                        # Only treat as genuine evidence if NOT advisory or negated!
                        if not is_advisory:
                            risk_flags.append(flag)
                            risk_evidence[flag] = sentence

        if risk_flags:
            quality_score = max(10, quality_score - 25)
            for flag in risk_flags:
                ev = risk_evidence.get(flag)
                if ev:
                    quality_reasons.append(f"⚠️ Risk flag '{flag}' detected from evidence: \"{ev}\" (-25)")
                else:
                    quality_reasons.append(f"⚠️ Risk flag '{flag}' detected (-25)")

        quality_score = max(0, min(100, quality_score))

        # 9. Derive Explainable Priority Score (0-100)
        # Priority = 0.45 * Match + 0.25 * Quality + 0.15 * Freshness + 0.10 * Contact + 0.05 * QuickApply
        freshness_val = 1.0
        if freshness_days == 1:
            freshness_val = 1.0
        elif freshness_days == 3:
            freshness_val = 0.8
        elif freshness_days == 7:
            freshness_val = 0.5
        else:
            freshness_val = 0.4

        freshness_pts = 15.0 * freshness_val
        contact_pts = 10.0 if has_contact else 0.0
        qa_pts = 5.0 if is_quick_apply else 0.0
        match_pts = 0.45 * match_score
        qual_pts = 0.25 * quality_score

        raw_priority = match_pts + qual_pts + freshness_pts + contact_pts + qa_pts
        if risk_flags:
            raw_priority = min(raw_priority, 40.0) # Penalize priority heavily if risk flag detected

        priority_score = int(round(max(0, min(100, raw_priority))))

        priority_reasons: List[str] = []
        if match_score >= 80:
            priority_reasons.append(f"High candidate match ({match_score}%)")
        elif match_score >= 60:
            priority_reasons.append(f"Moderate candidate match ({match_score}%)")
        else:
            priority_reasons.append(f"Low candidate match ({match_score}%)")

        if quality_score >= 70:
            priority_reasons.append("High-quality, transparent job listing")
        if has_contact:
            priority_reasons.append("Direct recruiter / hiring contact available")
        if freshness_days and freshness_days <= 3:
            priority_reasons.append(f"Fresh listing (posted within {freshness_days} days)")
        if is_quick_apply:
            priority_reasons.append("1-click Quick Apply enabled")
        if risk_flags:
            priority_reasons.append(f"Demoted priority: risk flags {risk_flags}")

        return JobQualityResult(
            quality_score=quality_score,
            risk_flags=risk_flags,
            risk_evidence=risk_evidence,
            quality_reasons=quality_reasons,
            priority_score=priority_score,
            priority_reasons=priority_reasons
        )


job_quality_scorer = JobQualityScorer()
