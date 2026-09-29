"""
Deterministic, explainable job description match scoring engine.
Follows an explicit 60/20/10/10 scoring contract with exact mathematical fallbacks.
"""

import re
from typing import List, Tuple, Optional, Set, Any
from pydantic import BaseModel, Field

from app.models.job import ResumeProfile
from app.platforms.naukri_helpers import normalize_token


class MatchResult(BaseModel):
    score: int = Field(..., ge=0, le=100)
    matched_skills: List[str] = Field(default_factory=list)
    missing_required: List[str] = Field(default_factory=list)
    matched_preferred: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    is_eligible: bool = True
    is_low_confidence_parse: bool = False


class MatchScorer:
    """
    Deterministic Match Scoring Engine:
      - Required Skills: 60 points
      - Preferred Skills: 20 points
      - Title Relevance: 10 points
      - Experience Alignment: 10 points
      Total = 100 points
      
    Documented Fallback Redistribution Rules:
      1. If no preferred skills in JD: 20 points redistributed to Required Skills (making Required Skills 80 points).
      2. If no experience specified in JD: Full 10 points awarded for Experience Alignment (neutral benefit).
      3. If zero identifiable skills in JD: score = round(70 * title_match_ratio + exp_pts), flagged with is_low_confidence_parse = True.
      4. Eligibility Rule: score >= min_threshold -> eligible; score < min_threshold -> ineligible.
    """

    COMMON_TECH_SKILLS = {
        "python", "javascript", "typescript", "react", "reactjs", "node", "nodejs",
        "express", "fastapi", "django", "flask", "html", "css", "sql", "postgresql",
        "mysql", "mongodb", "redis", "docker", "kubernetes", "aws", "gcp", "azure",
        "git", "rest", "graphql", "tailwind", "nextjs", "vue", "angular", "c++",
        "java", "spring", "springboot", "spring boot", "golang", "rust", "ci/cd", "linux", "agile", "scrum",
        ".net", "dotnet", "c#", "csharp", "asp.net", "php", "laravel", "ruby", "rails",
        "flutter", "dart", "salesforce", "swift", "kotlin", "scala", "elixir",
        "react native", "redux", "vite", "supabase", "firebase", "postman", "prisma"
    }

    def score_job(
        self,
        job_title: str,
        jd_text: str,
        profile: ResumeProfile,
        min_threshold: int = 60,
        excluded_keywords: Optional[List[str]] = None,
        max_experience_gap: Optional[float] = None
    ) -> MatchResult:
        if not jd_text or not profile:
            # Empty input edge cases
            return MatchResult(
                score=0,
                is_eligible=(min_threshold == 0),
                reasons=["Empty job description or profile provided."],
                is_low_confidence_parse=True
            )

        candidate_skills = {normalize_token(s) for s in profile.skills if s}
        # Also add words from work experience titles or summary
        if profile.work_experience:
            for exp in profile.work_experience:
                for word in exp.title.lower().split():
                    candidate_skills.add(normalize_token(word))

        # Check if job title explicitly specifies a core technology family where candidate has 0 skills
        title_lower = job_title.lower()
        title_core_techs = [
            ("dotnet", [".net", "dotnet", "dot net", "asp.net", "c#", "csharp", "vb.net"], ["dotnet", ".net", "dot net", "aspnet", "c#", "csharp", "vbnet"]),
            ("java", ["java full stack", "core java", "java developer", "spring boot", "springboot", "j2ee"], ["java", "spring", "springboot", "spring boot", "hibernate", "j2ee"]),
            ("angular", ["angular developer", "angularjs developer"], ["angular", "angularjs"]),
            ("php", ["php developer", "laravel developer", "wordpress developer"], ["php", "laravel", "wordpress"]),
            ("flutter", ["flutter developer", "dart developer"], ["flutter", "dart"]),
            ("salesforce", ["salesforce", "sfdc"], ["salesforce", "sfdc"]),
        ]
        for tech_name, patterns, skills_req in title_core_techs:
            if any(p in title_lower for p in patterns):
                has_tech = any(self._skill_matches(s, candidate_skills) for s in skills_req)
                if not has_tech:
                    return MatchResult(
                        score=25,
                        matched_skills=[],
                        missing_required=skills_req[:2],
                        matched_preferred=[],
                        reasons=[f"Core technology '{tech_name}' required by title but absent from candidate resume."],
                        is_eligible=False,
                        is_low_confidence_parse=False
                    )

        # 1. Parse JD Skills & Sections
        required_skills, preferred_skills = self._extract_jd_skills(jd_text)
        has_preferred_section = len(preferred_skills) > 0

        # 2. Score Title Relevance (10 pts)
        title_ratio = self._calculate_title_relevance(job_title, profile)
        title_pts = 10.0 * title_ratio

        # 3. Score Experience Alignment (10 pts)
        jd_min_exp = self._extract_experience_requirement(jd_text)
        candidate_exp = float(profile.years_of_experience)

        has_exp_requirement = jd_min_exp is not None
        if has_exp_requirement:
            if candidate_exp >= jd_min_exp:
                exp_pts = 10.0
            elif candidate_exp >= (jd_min_exp - 1.0):
                exp_pts = 5.0
            else:
                exp_pts = 0.0
        else:
            # Fallback 2: No experience specified -> neutral full 10 points
            exp_pts = 10.0

        # Disqualification checks
        disqualification_notes = []
        is_hard_disqualified = False
        if excluded_keywords:
            text_to_check = f"{job_title.lower()} {jd_text.lower()}"
            for kw in excluded_keywords:
                if kw and re.search(rf"\b{re.escape(kw.lower())}\b", text_to_check):
                    is_hard_disqualified = True
                    disqualification_notes.append(f"Excluded keyword '{kw}' detected in job posting.")

        if max_experience_gap is not None and jd_min_exp is not None:
            if (jd_min_exp - candidate_exp) > max_experience_gap:
                is_hard_disqualified = True
                disqualification_notes.append(
                    f"Experience requirement ({jd_min_exp} yrs) exceeds candidate's experience ({candidate_exp} yrs) by more than allowed gap ({max_experience_gap} yrs)."
                )

        # 4. Handle Fallback 3: Zero identifiable skills in JD
        if not required_skills and not preferred_skills:
            score = int(round(70.0 * title_ratio + exp_pts))
            score = max(0, min(100, score))
            reasons = [
                "Low confidence parse: no specific technology skills detected in JD.",
                f"Title relevance: {int(round(title_ratio * 100))}% ({title_pts:.1f} pts)",
                f"Experience alignment: {exp_pts:.1f} pts"
            ]
            reasons.extend(disqualification_notes)
            return MatchResult(
                score=score,
                matched_skills=[],
                missing_required=[],
                matched_preferred=[],
                reasons=reasons,
                is_eligible=(score >= min_threshold and not is_hard_disqualified),
                is_low_confidence_parse=True
            )

        # Calculate skill matches
        matched_req = [s for s in required_skills if self._skill_matches(s, candidate_skills)]
        missing_req = [s for s in required_skills if not self._skill_matches(s, candidate_skills)]

        matched_pref = [s for s in preferred_skills if self._skill_matches(s, candidate_skills)]

        # Base match ratios
        base_req_ratio = (len(matched_req) / len(required_skills)) if required_skills else 1.0
        # If candidate matches 2+ core skills, give graceful floor so extra JD buzzwords don't disqualify
        if len(matched_req) >= 3:
            req_ratio = max(base_req_ratio, 0.75)
        elif len(matched_req) >= 2:
            req_ratio = max(base_req_ratio, 0.60)
        else:
            req_ratio = base_req_ratio

        base_pref_ratio = (len(matched_pref) / len(preferred_skills)) if preferred_skills else 1.0
        pref_ratio = base_pref_ratio

        # Apply Fallback 1: If no preferred skills in JD, redistribute 20 pts to Required (80 pts total)
        if has_preferred_section:
            req_weight = 60.0
            pref_weight = 20.0
            skills_pts = (req_weight * req_ratio) + (pref_weight * pref_ratio)
        else:
            req_weight = 80.0
            skills_pts = req_weight * req_ratio

        total_score = int(round(skills_pts + title_pts + exp_pts))
        total_score = max(0, min(100, total_score))

        reasons = [
            f"Required skills matched: {len(matched_req)}/{len(required_skills)}",
            f"Title relevance: {int(round(title_ratio * 100))}% ({title_pts:.1f} pts)",
            f"Experience alignment: {exp_pts:.1f} pts (Req: {jd_min_exp or 'unspecified'} yrs, Candidate: {candidate_exp} yrs)"
        ]
        if has_preferred_section:
            reasons.append(f"Preferred skills matched: {len(matched_pref)}/{len(preferred_skills)}")
        reasons.extend(disqualification_notes)

        return MatchResult(
            score=total_score,
            matched_skills=matched_req,
            missing_required=missing_req,
            matched_preferred=matched_pref,
            reasons=reasons,
            is_eligible=(total_score >= min_threshold and not is_hard_disqualified),
            is_low_confidence_parse=False
        )

    def score_jobs_batch(
        self,
        jobs: List[Any],
        profile: ResumeProfile,
        min_threshold: int = 60,
        excluded_keywords: Optional[List[str]] = None,
        max_experience_gap: Optional[float] = None
    ) -> List[MatchResult]:
        """Score a collection of jobs in batch against the candidate profile."""
        results: List[MatchResult] = []
        for item in jobs:
            title = ""
            jd = ""
            if isinstance(item, tuple) and len(item) >= 2:
                title, jd = item[0], item[1]
            elif hasattr(item, "title") and hasattr(item, "description"):
                title = item.title
                jd = item.description or ""
            elif isinstance(item, dict):
                title = item.get("title") or item.get("job_title") or ""
                jd = item.get("description") or item.get("jd_text") or ""
            
            res = self.score_job(
                job_title=title,
                jd_text=jd,
                profile=profile,
                min_threshold=min_threshold,
                excluded_keywords=excluded_keywords,
                max_experience_gap=max_experience_gap
            )
            results.append(res)
        return results


    def _normalize_skill(self, skill: str) -> str:
        s = skill.strip().lower()
        replacements = {
            "c#": "csharp",
            "c++": "cpp",
            ".net": "dotnet",
            "dot net": "dotnet",
            "asp.net": "aspnet",
            "react.js": "react",
            "reactjs": "react",
            "node.js": "node",
            "nodejs": "node",
            "express.js": "express",
            "expressjs": "express",
            "next.js": "nextjs",
            "nextjs": "nextjs",
            "vue.js": "vue",
            "vuejs": "vue",
            "angular.js": "angular",
            "angularjs": "angular",
            "spring boot": "springboot",
            "html5": "html",
            "css3": "css",
            "tailwind css": "tailwind",
            "tailwindcss": "tailwind",
            "rest api": "rest",
            "rest apis": "rest",
            "restful": "rest",
            "restful api": "rest",
            "restful apis": "rest",
            "redux toolkit": "redux",
            "postgres": "postgresql",
            "mongo": "mongodb",
        }
        for k, v in replacements.items():
            if s == k:
                return v
        return normalize_token(s)

    def _skill_matches(self, skill: str, candidate_skills: Set[str]) -> bool:
        """Check direct or safe substring match against normalized candidate skills."""
        norm = self._normalize_skill(skill)
        if not norm:
            return False

        norm_candidate = {self._normalize_skill(cs) for cs in candidate_skills if cs}

        if norm in norm_candidate:
            return True

        # Only allow substring matching for descriptive tokens (length > 3)
        # to prevent short tokens like 'c', 'net', 'sql', 'git', 'go' from falsely matching inside unrelated words
        if len(norm) > 3:
            for cs in norm_candidate:
                if len(cs) > 3 and (norm == cs or f" {norm} " in f" {cs} " or norm in cs or cs in norm):
                    return True

        return False

    def _calculate_title_relevance(self, job_title: str, profile: ResumeProfile) -> float:
        """Compute keyword overlap between job title and candidate's title / summary."""
        title_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", job_title.lower()))
        if not title_words:
            return 1.0

        candidate_tokens = set()
        if profile.work_experience:
            for exp in profile.work_experience:
                candidate_tokens.update(re.findall(r"\b[a-zA-Z]{3,}\b", exp.title.lower()))
        if profile.summary:
            candidate_tokens.update(re.findall(r"\b[a-zA-Z]{3,}\b", profile.summary.lower()))
        for skill in profile.skills:
            candidate_tokens.update(re.findall(r"\b[a-zA-Z]{3,}\b", skill.lower()))

        overlap = title_words.intersection(candidate_tokens)
        return min(1.0, len(overlap) / max(1, len(title_words)))

    def _extract_jd_skills(self, jd_text: str) -> Tuple[List[str], List[str]]:
        """Identify required and preferred skills from text sections."""
        text_lower = jd_text.lower()

        # Check for Preferred / Nice to have section
        pref_split = re.split(r"(?:nice to have|preferred|good to have|bonus|plus):", text_lower, maxsplit=1)
        
        required_text = pref_split[0]
        preferred_text = pref_split[1] if len(pref_split) > 1 else ""

        required_skills = self._find_known_skills(required_text)
        preferred_skills = self._find_known_skills(preferred_text)

        # If no skills found from known list, extract bullet points or keywords
        if not required_skills:
            # Fallback pattern extraction
            words = set(re.findall(r"\b[a-zA-Z]{2,15}\b", required_text))
            detected = words.intersection(self.COMMON_TECH_SKILLS)
            required_skills = list(detected)

        return required_skills, preferred_skills

    def _find_known_skills(self, text: str) -> List[str]:
        if not text:
            return []
        found = []
        text_lower = text.lower()
        for skill in self.COMMON_TECH_SKILLS:
            # Special regex for skills with non-alphanumeric symbols
            if skill in [".net", "c#", "c++", "asp.net"]:
                pattern = r"(?:^|[\s,;/()\.])" + re.escape(skill) + r"(?:[\s,;/()\.?!]|$)"
                if re.search(pattern, text_lower):
                    found.append(skill)
            else:
                if re.search(r"\b" + re.escape(skill) + r"\b", text_lower):
                    found.append(skill)
        return found

    def _extract_experience_requirement(self, text: str) -> Optional[float]:
        """Extract minimum years of experience from text like '3+ years', '2-5 years'."""
        patterns = [
            r"(\d+)(?:\+|\s*to\s*\d+)?\s*(?:years|yrs)\b",
            r"(?:min|minimum|at least)\s*(\d+)\s*(?:years|yrs)\b",
            r"(\d+)\s*-\s*\d+\s*(?:years|yrs)\b"
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except (ValueError, IndexError):
                    pass
        return None


match_scorer = MatchScorer()
