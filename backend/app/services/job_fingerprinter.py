"""
Canonical Job Fingerprinting & Idempotency Engine.
Prevents duplicate applications caused by URL query mutations, tracking parameters, or cross-portal syndication.
"""

import re
import hashlib
from urllib.parse import urlparse, urlunparse
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class JobIdentity(BaseModel):
    fingerprint: str = Field(description="SHA-256 canonical hash of the job posting")
    idempotency_key: str = Field(description="Deterministic key combining candidate identity and job fingerprint")
    normalized_title: str
    normalized_company: str
    normalized_location: str
    canonical_url: str


class JobFingerprinter:
    """
    Computes deterministic, canonical fingerprints for job postings.
    Normalizes company names, job titles, locations, and descriptions.
    """

    STOPWORDS = {
        "inc", "inc.", "llc", "ltd", "corp", "corporation", "co", "technologies",
        "solutions", "services", "global", "pvt", "private", "limited", "the", "a", "an"
    }

    @classmethod
    def normalize_company(cls, company: str) -> str:
        if not company:
            return ""
        # Remove special characters, lowercase, remove legal corporate suffixes
        clean = re.sub(r"[^\w\s]", "", company.lower()).strip()
        tokens = [t for t in clean.split() if t not in cls.STOPWORDS]
        return " ".join(tokens) or clean

    @classmethod
    def normalize_title(cls, title: str) -> str:
        if not title:
            return ""
        clean = re.sub(r"[^\w\s]", " ", title.lower()).strip()
        # Standardize common tech title synonyms
        clean = re.sub(r"\bsr\.?\b", "senior", clean)
        clean = re.sub(r"\bjr\.?\b", "junior", clean)
        clean = re.sub(r"\beng\.?\b", "engineer", clean)
        clean = re.sub(r"\bdev\.?\b", "developer", clean)
        clean = re.sub(r"\bswe\b", "software engineer", clean)
        tokens = [t for t in clean.split() if t not in {"the", "a", "an", "for", "in"}]
        return " ".join(tokens)

    @classmethod
    def normalize_location(cls, location: str) -> str:
        if not location:
            return "remote"
        clean = re.sub(r"[^\w\s]", " ", location.lower()).strip()
        if any(term in clean for term in ["remote", "work from home", "wfh", "anywhere"]):
            return "remote"
        # Keep city / primary token
        parts = clean.split()
        return parts[0] if parts else clean

    @classmethod
    def normalize_url(cls, raw_url: str) -> str:
        """Strip tracking parameters (utm_*, ref, trackingId, etc.) from job URLs."""
        if not raw_url:
            return ""
        try:
            parsed = urlparse(raw_url.strip())
            # Reconstruct URL without query string or fragment
            cleaned_url = urlunparse((
                parsed.scheme,
                parsed.netloc.lower(),
                parsed.path.rstrip("/"),
                "",
                "",
                ""
            ))
            return cleaned_url
        except Exception:
            return raw_url.strip()

    @classmethod
    def compute_description_hash(cls, description: Optional[str]) -> str:
        """Computes a short hash of the core description content to catch reposts."""
        if not description:
            return "empty"
        # Take first 400 alphanumeric characters
        alnum = re.sub(r"\W+", "", description.lower())[:400]
        return hashlib.sha256(alnum.encode("utf-8")).hexdigest()[:12]

    @classmethod
    def generate_fingerprint(
        cls,
        company: str,
        title: str,
        location: str = "remote",
        job_url: str = "",
        description: Optional[str] = None,
        platform: str = "general"
    ) -> str:
        """
        Generates canonical SHA-256 fingerprint.
        Formula: SHA-256(norm_company | norm_title | norm_location | desc_hash)
        """
        norm_company = cls.normalize_company(company)
        norm_title = cls.normalize_title(title)
        norm_location = cls.normalize_location(location)
        desc_hash = cls.compute_description_hash(description)

        raw = f"{norm_company}|{norm_title}|{norm_location}|{desc_hash}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def build_identity(
        cls,
        candidate_id: str,
        company: str,
        title: str,
        location: str = "remote",
        job_url: str = "",
        description: Optional[str] = None,
        platform: str = "general"
    ) -> JobIdentity:
        """Constructs full JobIdentity including candidate-specific idempotency key."""
        norm_company = cls.normalize_company(company)
        norm_title = cls.normalize_title(title)
        norm_location = cls.normalize_location(location)
        canonical_url = cls.normalize_url(job_url)
        fingerprint = cls.generate_fingerprint(
            company=company,
            title=title,
            location=location,
            job_url=job_url,
            description=description,
            platform=platform
        )
        # Idempotency key binds candidate to fingerprint
        idempotency_raw = f"{candidate_id}:{fingerprint}"
        idempotency_key = hashlib.sha256(idempotency_raw.encode("utf-8")).hexdigest()

        return JobIdentity(
            fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            normalized_title=norm_title,
            normalized_company=norm_company,
            normalized_location=norm_location,
            canonical_url=canonical_url
        )


job_fingerprinter = JobFingerprinter()
