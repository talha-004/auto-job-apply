"""
Candidate Fact Ledger & Provenance Models.
Enforces the core principle: "No Evidence -> No Claim -> No Auto-Submission".
Every statement submitted on behalf of a candidate must be backed by a verified CandidateFact.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class FactCategory(str, Enum):
    TECHNICAL_SKILL = "technical_skill"
    WORK_EXPERIENCE = "work_experience"
    EDUCATION = "education"
    AUTHORIZATION = "authorization"
    COMPENSATION = "compensation"
    PREFERENCE = "preference"
    CUSTOM = "custom"


class VerificationStatus(str, Enum):
    VERIFIED_BY_USER = "verified_by_user"
    EXTRACTED_FROM_RESUME = "extracted_from_resume"
    INFERRED_LOW_CONFIDENCE = "inferred_low_confidence"
    UNVERIFIED = "unverified"


class CandidateFact(BaseModel):
    fact_id: str = Field(description="Unique deterministic or generated identifier for the fact")
    category: FactCategory
    subject: str = Field(description="Normalized skill or domain entity, e.g. 'Python', 'WorkAuthorization', 'NoticePeriod'")
    value: Any = Field(description="Canonical representation, e.g. 3.5, 'Yes', '30 days'")
    numeric_value: Optional[float] = Field(default=None, description="Extracted numerical metric (e.g., years of experience)")
    verification_status: VerificationStatus = Field(default=VerificationStatus.EXTRACTED_FROM_RESUME)
    source_document: Optional[str] = Field(default=None, description="Origin filename or vault reference")
    source_span: Optional[str] = Field(default=None, description="Exact text excerpt from resume or user input")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def is_verified(self) -> bool:
        return self.verification_status in (
            VerificationStatus.VERIFIED_BY_USER,
            VerificationStatus.EXTRACTED_FROM_RESUME,
        )


class FactLedger(BaseModel):
    facts: List[CandidateFact] = Field(default_factory=list)

    def add_fact(self, fact: CandidateFact) -> None:
        # Avoid duplicate fact IDs
        for i, existing in enumerate(self.facts):
            if existing.fact_id == fact.fact_id or (
                existing.category == fact.category and existing.subject.lower() == fact.subject.lower()
            ):
                self.facts[i] = fact
                return
        self.facts.append(fact)

    def get_fact(self, subject: str, category: Optional[FactCategory] = None) -> Optional[CandidateFact]:
        sub_norm = subject.strip().lower()
        for fact in self.facts:
            if category and fact.category != category:
                continue
            if fact.subject.strip().lower() == sub_norm:
                return fact
        return None

    def get_facts_by_category(self, category: FactCategory) -> List[CandidateFact]:
        return [f for f in self.facts if f.category == category]


class VerificationResult(BaseModel):
    is_valid: bool
    requires_human_review: bool
    confidence: float = 1.0
    evidence_fact: Optional[CandidateFact] = None
    reason: str = ""
    suggested_answer: Optional[str] = None
