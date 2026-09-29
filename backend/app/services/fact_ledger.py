"""
Fact Ledger Service.
Extracts, registers, and manages verified candidate facts from ResumeProfile and QAVault.
Provides fast lookups for question-answering provenance and claim verification.
"""

import hashlib
from typing import List, Optional, Dict, Any
from app.models.fact_ledger import (
    CandidateFact,
    FactCategory,
    FactLedger,
    VerificationStatus,
)
from app.models.job import ResumeProfile, QAVault


class FactLedgerService:
    def __init__(self, ledger: Optional[FactLedger] = None):
        self.ledger = ledger or FactLedger()

    def generate_fact_id(self, category: FactCategory, subject: str) -> str:
        raw = f"{category.value}:{subject.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def build_from_profile(self, profile: ResumeProfile, source_doc: str = "master_resume") -> FactLedger:
        """
        Decomposes a structured ResumeProfile into atomic, verifiable candidate facts.
        """
        self.ledger = FactLedger()

        # 1. Total Years of Experience
        exp_id = self.generate_fact_id(FactCategory.WORK_EXPERIENCE, "total_experience_years")
        self.ledger.add_fact(
            CandidateFact(
                fact_id=exp_id,
                category=FactCategory.WORK_EXPERIENCE,
                subject="total_experience_years",
                value=profile.years_of_experience,
                numeric_value=float(profile.years_of_experience),
                verification_status=VerificationStatus.EXTRACTED_FROM_RESUME,
                source_document=source_doc,
                source_span=f"Parsed total experience: {profile.years_of_experience} years",
            )
        )

        # 2. Individual Skills
        for skill in profile.skills:
            if not skill or not skill.strip():
                continue
            skill_clean = skill.strip()
            fact_id = self.generate_fact_id(FactCategory.TECHNICAL_SKILL, skill_clean)
            self.ledger.add_fact(
                CandidateFact(
                    fact_id=fact_id,
                    category=FactCategory.TECHNICAL_SKILL,
                    subject=skill_clean,
                    value=True,
                    numeric_value=profile.years_of_experience,  # default max experience for listed skill
                    verification_status=VerificationStatus.EXTRACTED_FROM_RESUME,
                    source_document=source_doc,
                    source_span=f"Skill listed in resume: {skill_clean}",
                )
            )

        # 3. Work Experience Roles
        for exp in profile.work_experience:
            subject = f"{exp.title} at {exp.company}"
            fact_id = self.generate_fact_id(FactCategory.WORK_EXPERIENCE, subject)
            self.ledger.add_fact(
                CandidateFact(
                    fact_id=fact_id,
                    category=FactCategory.WORK_EXPERIENCE,
                    subject=subject,
                    value={"company": exp.company, "title": exp.title, "duration": f"{exp.start_date} - {exp.end_date}"},
                    verification_status=VerificationStatus.EXTRACTED_FROM_RESUME,
                    source_document=source_doc,
                    source_span=f"{exp.title} ({exp.start_date} - {exp.end_date}) at {exp.company}: {exp.description[:100]}",
                )
            )

        # 4. Education
        for edu in profile.education:
            subject = f"{edu.degree} in {edu.field}".strip()
            fact_id = self.generate_fact_id(FactCategory.EDUCATION, subject)
            self.ledger.add_fact(
                CandidateFact(
                    fact_id=fact_id,
                    category=FactCategory.EDUCATION,
                    subject=subject,
                    value={"institution": edu.institution, "graduation_year": edu.graduation_year},
                    verification_status=VerificationStatus.EXTRACTED_FROM_RESUME,
                    source_document=source_doc,
                    source_span=f"{edu.degree} from {edu.institution} ({edu.graduation_year})",
                )
            )

        # 5. Q&A Vault Facts (Standard Authorization, Notice Period, CTC)
        qa = profile.qa_vault or QAVault()
        self._ingest_qa_vault(qa)

        return self.ledger

    def _ingest_qa_vault(self, qa: QAVault) -> None:
        """Helper to index verified QA Vault entries."""
        qa_entries = [
            (FactCategory.AUTHORIZATION, "work_authorization", qa.work_authorization, None),
            (FactCategory.AUTHORIZATION, "require_sponsorship", qa.require_sponsorship, None),
            (FactCategory.PREFERENCE, "willing_to_relocate", qa.willing_to_relocate, None),
            (FactCategory.PREFERENCE, "notice_period_days", qa.notice_period_days, float(qa.notice_period_days)),
            (FactCategory.COMPENSATION, "expected_ctc_lpa", qa.expected_ctc_lpa, float(qa.expected_ctc_lpa) if qa.expected_ctc_lpa else None),
            (FactCategory.COMPENSATION, "current_ctc_lpa", qa.current_ctc_lpa, float(qa.current_ctc_lpa) if qa.current_ctc_lpa else None),
        ]

        for cat, subject, val, num_val in qa_entries:
            fact_id = self.generate_fact_id(cat, subject)
            self.ledger.add_fact(
                CandidateFact(
                    fact_id=fact_id,
                    category=cat,
                    subject=subject,
                    value=val,
                    numeric_value=num_val,
                    verification_status=VerificationStatus.VERIFIED_BY_USER,
                    source_document="qa_vault",
                    source_span=f"Pre-approved QA Vault default: {subject}={val}",
                )
            )

        # Custom QA pairs
        for q_key, q_val in qa.custom_qa.items():
            fact_id = self.generate_fact_id(FactCategory.CUSTOM, q_key)
            self.ledger.add_fact(
                CandidateFact(
                    fact_id=fact_id,
                    category=FactCategory.CUSTOM,
                    subject=q_key,
                    value=q_val,
                    verification_status=VerificationStatus.VERIFIED_BY_USER,
                    source_document="qa_vault_custom",
                    source_span=f"User pre-set answer: {q_val}",
                )
            )

    def add_fact(self, fact: CandidateFact) -> None:
        self.ledger.add_fact(fact)

    def query_skill(self, skill_name: str) -> Optional[CandidateFact]:
        return self.ledger.get_fact(skill_name, category=FactCategory.TECHNICAL_SKILL)

    def get_total_experience_years(self) -> float:
        fact = self.ledger.get_fact("total_experience_years", category=FactCategory.WORK_EXPERIENCE)
        if fact and fact.numeric_value is not None:
            return fact.numeric_value
        return 0.0


fact_ledger_service = FactLedgerService()

