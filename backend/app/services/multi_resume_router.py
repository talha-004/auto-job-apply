"""
Dynamic Multi-Resume Auto-Routing Service.
Manages specialized resume variants (e.g. Full Stack, Backend Python, AI/ML)
and dynamically routes the highest-matching resume PDF for each specific job posting.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from app.core.config import settings
from app.core.logger import logger, broadcaster, LogLevel
from app.models.job import ResumeProfile
from app.services.ats_scorer import ats_scorer, ATSScorecard
from app.platforms.naukri_helpers import normalize_token


class MultiResumeRouterService:
    """
    Evaluates candidate resume variants against target job descriptions and selects
    the highest ATS-scoring resume variant for submission.
    """

    def __init__(self, registry_file: Optional[Path] = None, resumes_dir: Optional[Path] = None):
        self.resumes_dir = resumes_dir or (settings.DATA_PATH / "resumes")
        self.registry_file = registry_file or (self.resumes_dir / "variants_registry.json")
        self.resumes_dir.mkdir(parents=True, exist_ok=True)

    def _load_registry(self) -> List[Dict[str, Any]]:
        if not self.registry_file.exists():
            # Initialize with default resume if available in standard data directory
            default_variants = []
            default_resume_path = settings.RESUME_FILE_PATH
            if self.resumes_dir == (settings.DATA_PATH / "resumes") and default_resume_path.exists():
                default_variants.append({
                    "id": "primary_fullstack",
                    "label": "Primary Full Stack Resume",
                    "filename": default_resume_path.name,
                    "file_path": str(default_resume_path.resolve()),
                    "target_keywords": ["python", "javascript", "react", "fastapi", "full stack", "sql"],
                    "skills": ["Python", "FastAPI", "React", "PostgreSQL", "JavaScript", "Docker"],
                    "is_default": True,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                self._save_registry(default_variants)
            return default_variants

        try:
            with open(self.registry_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading resume variants registry: {e}")
            return []

    def _save_registry(self, variants: List[Dict[str, Any]]):
        try:
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(variants, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving resume variants registry: {e}")

    def list_variants(self) -> List[Dict[str, Any]]:
        """List all available resume variants with their metadata."""
        return self._load_registry()

    def register_variant(
        self,
        variant_id: str,
        label: str,
        file_path: Path,
        target_keywords: Optional[List[str]] = None,
        skills: Optional[List[str]] = None,
        is_default: bool = False
    ) -> Dict[str, Any]:
        """Register or update a specialized resume variant."""
        variants = self._load_registry()
        # Remove existing if same ID
        variants = [v for v in variants if v.get("id") != variant_id]

        if is_default:
            for v in variants:
                v["is_default"] = False

        record = {
            "id": variant_id,
            "label": label,
            "filename": file_path.name,
            "file_path": str(file_path.resolve()),
            "target_keywords": target_keywords or [],
            "skills": skills or [],
            "is_default": is_default,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        variants.append(record)
        self._save_registry(variants)
        logger.info(f"[MultiResumeRouter] Registered variant '{label}' ({variant_id}) -> {file_path}")
        return record

    def route_best_resume(
        self,
        job_title: str,
        job_description: str
    ) -> Dict[str, Any]:
        """
        Calculates ATS keyword overlap for all registered resume variants and selects
        the best-matching resume for the given job.
        """
        variants = self._load_registry()
        if not variants:
            default_path = str(settings.RESUME_FILE_PATH.resolve())
            return {
                "selected_variant_id": "default",
                "label": "Default Resume",
                "file_path": default_path,
                "match_score": 75.0,
                "matched_keywords": [],
                "justification": "No specific variants configured; using primary default resume."
            }

        if len(variants) == 1:
            v = variants[0]
            return {
                "selected_variant_id": v["id"],
                "label": v["label"],
                "file_path": v["file_path"],
                "match_score": 80.0,
                "matched_keywords": v.get("target_keywords", []),
                "justification": f"Single variant '{v['label']}' selected."
            }

        # Score each variant against JD
        jd_text = f"{job_title} {job_description}".lower()
        scored_variants = []

        for v in variants:
            variant_skills = v.get("skills", [])
            target_kws = v.get("target_keywords", [])
            all_candidate_terms = {normalize_token(t) for t in (variant_skills + target_kws)}

            # Extract JD tech keywords
            jd_keywords = ats_scorer.extract_keywords_from_jd(jd_text)
            matched = [kw for kw in jd_keywords if normalize_token(kw) in all_candidate_terms]
            
            # Title alignment boost
            title_boost = 0.0
            for kw in target_kws:
                if kw.lower() in job_title.lower():
                    title_boost += 15.0

            if jd_keywords:
                base_score = (len(matched) / len(jd_keywords)) * 100.0
            else:
                base_score = 70.0

            total_score = min(100.0, base_score + title_boost)
            scored_variants.append({
                "variant": v,
                "score": round(total_score, 1),
                "matched_keywords": matched
            })

        # Sort descending by score
        scored_variants.sort(key=lambda x: x["score"], reverse=True)
        winner = scored_variants[0]
        v_info = winner["variant"]

        justification = (
            f"Selected '{v_info['label']}' with {winner['score']}% ATS score "
            f"({len(winner['matched_keywords'])} matching keywords: {', '.join(winner['matched_keywords'][:5])})."
        )

        return {
            "selected_variant_id": v_info["id"],
            "label": v_info["label"],
            "file_path": v_info["file_path"],
            "match_score": winner["score"],
            "matched_keywords": winner["matched_keywords"],
            "justification": justification
        }


multi_resume_router = MultiResumeRouterService()
