"""
ATS Keyword Gap Analyzer & Scorecard Engine.
Extracts hard skills, frameworks, cloud technologies, and qualifications from job descriptions,
computes a normalized ATS Match Score, and flags keyword gaps before resume generation.
"""

import re
from typing import Dict, Any, List, Set, Optional, Tuple
from pydantic import BaseModel, Field

from app.models.job import ResumeProfile
from app.platforms.naukri_helpers import normalize_token


class ATSScorecard(BaseModel):
    overall_score: float = Field(ge=0.0, le=100.0)
    tier: str
    matched_keywords: List[str] = Field(default_factory=list)
    partial_keywords: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class ATSScorer:
    """
    Evaluates candidate resume profile alignment against target job descriptions,
    simulating modern Applicant Tracking Systems (Workday, Taleo, Greenhouse, Lever).
    """

    KNOWN_TECH_KEYWORDS = {
        "python", "javascript", "typescript", "react", "next.js", "node.js",
        "fastapi", "django", "flask", "express", "sql", "postgresql", "mysql",
        "mongodb", "redis", "docker", "kubernetes", "aws", "gcp", "azure",
        "git", "ci/cd", "rest", "restful", "graphql", "playwright", "selenium", "pytest",
        "machine learning", "deep learning", "nlp", "llm", "pandas", "numpy",
        "scikit-learn", "tensorflow", "pytorch", "microservices", "terraform",
        "linux", "kafka", "elasticsearch", "html", "css", "tailwind", "celery"
    }

    def __init__(self):
        pass

    def extract_keywords_from_jd(self, job_description: str) -> List[str]:
        """Extracts recognized technical keywords and key domain skills from job description text."""
        jd_lower = job_description.lower()
        extracted: Set[str] = set()

        for kw in self.KNOWN_TECH_KEYWORDS:
            # Word boundary regex search (also matches variants like rest/restful)
            escaped = re.escape(kw)
            if re.search(rf"\b{escaped}", jd_lower):
                extracted.add(kw)

        # Extract potential custom capitalized skill tokens (e.g. specialized tools or frameworks)
        potential_skills = re.findall(r"\b([A-Z][a-zA-Z0-9_\-\.]{2,15})\b", job_description)
        for token in potential_skills:
            t_norm = token.lower()
            if t_norm in self.KNOWN_TECH_KEYWORDS:
                extracted.add(t_norm)

        return sorted(list(extracted))

    def evaluate_resume_ats_match(
        self,
        profile: ResumeProfile,
        job_description: str,
        tailored_summary: Optional[str] = None
    ) -> ATSScorecard:
        """
        Calculates ATS keyword match percentage and categorizes keywords into
        matched, partial, and missing.
        """
        jd_keywords = self.extract_keywords_from_jd(job_description)
        if not jd_keywords:
            return ATSScorecard(
                overall_score=85.0,
                tier="STRONG_MATCH",
                matched_keywords=[],
                partial_keywords=[],
                missing_keywords=[],
                recommendations=["Job description did not contain recognized technical keywords."]
            )

        # Candidate corpus: skills, experiences, projects, summary
        candidate_skills = {normalize_token(s) for s in profile.skills}
        candidate_corpus_tokens: Set[str] = set(candidate_skills)

        # Ingest summary
        full_summary = f"{profile.summary} {tailored_summary or ''}".lower()
        for kw in self.KNOWN_TECH_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", full_summary):
                candidate_corpus_tokens.add(normalize_token(kw))

        # Ingest experience description, bullets & titles
        for exp in profile.work_experience:
            bullets = getattr(exp, "bullets", None)
            desc_text = " ".join(bullets) if bullets else getattr(exp, "description", "")
            exp_text = f"{exp.title} {exp.company} {desc_text}".lower()
            for kw in self.KNOWN_TECH_KEYWORDS:
                if re.search(rf"\b{re.escape(kw)}\b", exp_text):
                    candidate_corpus_tokens.add(normalize_token(kw))

        matched: List[str] = []
        partial: List[str] = []
        missing: List[str] = []

        for kw in jd_keywords:
            norm_kw = normalize_token(kw)
            if norm_kw in candidate_corpus_tokens:
                matched.append(kw)
            elif any(norm_kw in token or token in norm_kw for token in candidate_corpus_tokens):
                partial.append(kw)
            else:
                missing.append(kw)

        # Weighted score: Matched = 1.0, Partial = 0.5, Missing = 0.0
        total_kws = len(jd_keywords)
        raw_score = (len(matched) * 1.0 + len(partial) * 0.5) / float(total_kws) * 100.0
        final_score = round(min(100.0, max(15.0, raw_score)), 1)

        # Determine Tier
        if final_score >= 85.0:
            tier = "STRONG_MATCH"
        elif final_score >= 70.0:
            tier = "COMPETITIVE_MATCH"
        elif final_score >= 50.0:
            tier = "MODERATE_MATCH"
        else:
            tier = "WEAK_MATCH"

        # Generate Actionable Recommendations
        recommendations: List[str] = []
        if missing:
            top_missing = missing[:4]
            recommendations.append(f"Consider highlighting experience with: {', '.join(top_missing)}.")
        if partial:
            recommendations.append(f"Clarify specific hands-on usage for partially matched areas: {', '.join(partial[:3])}.")
        if not recommendations:
            recommendations.append("Excellent keyword coverage across all required core technologies.")

        return ATSScorecard(
            overall_score=final_score,
            tier=tier,
            matched_keywords=matched,
            partial_keywords=partial,
            missing_keywords=missing,
            recommendations=recommendations
        )


# Global service instance
ats_scorer = ATSScorer()
