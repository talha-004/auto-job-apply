"""
Claim Verifier Engine.
Prevents ungrounded, inflated, or hallucinated claims from reaching employers.
Evaluates proposed screening answers against the verified Candidate Fact Ledger.
"""

import re
from typing import Optional, Tuple
from app.models.fact_ledger import (
    FactLedger,
    CandidateFact,
    FactCategory,
    VerificationResult,
)


class ClaimVerifier:
    def __init__(self, ledger: FactLedger):
        self.ledger = ledger

    def verify_answer(self, question: str, proposed_answer: str) -> VerificationResult:
        """
        Validates proposed answer against verified facts.
        Blocks unverified claims, numerical inflations, and authorization contradictions.
        """
        q_lower = question.lower()
        ans_lower = proposed_answer.lower()

        # 1. Verification of Legal Authorization & Sponsorship
        if any(term in q_lower for term in ["authorized to work", "legally authorized", "work permit", "work authorization"]):
            auth_fact = self.ledger.get_fact("work_authorization", category=FactCategory.AUTHORIZATION)
            if auth_fact:
                expected = str(auth_fact.value).lower()
                if ("yes" in expected and "no" in ans_lower) or ("no" in expected and "yes" in ans_lower):
                    return VerificationResult(
                        is_valid=False,
                        requires_human_review=True,
                        confidence=0.95,
                        evidence_fact=auth_fact,
                        reason=f"Proposed answer contradicts verified work authorization fact ({auth_fact.value})",
                        suggested_answer=str(auth_fact.value),
                    )
            return VerificationResult(is_valid=True, requires_human_review=False, confidence=1.0)

        if any(term in q_lower for term in ["sponsorship", "require visa", "visa sponsorship"]):
            spons_fact = self.ledger.get_fact("require_sponsorship", category=FactCategory.AUTHORIZATION)
            if spons_fact:
                expected = str(spons_fact.value).lower()
                if ("yes" in expected and "no" in ans_lower) or ("no" in expected and "yes" in ans_lower):
                    return VerificationResult(
                        is_valid=False,
                        requires_human_review=True,
                        confidence=0.95,
                        evidence_fact=spons_fact,
                        reason=f"Proposed answer contradicts verified sponsorship fact ({spons_fact.value})",
                        suggested_answer=str(spons_fact.value),
                    )
            return VerificationResult(is_valid=True, requires_human_review=False, confidence=1.0)

        # 2. Verification of Experience Duration (e.g. "Do you have 5+ years...")
        years_in_question = self._extract_years(question)
        years_in_answer = self._extract_years(proposed_answer)
        total_exp_fact = self.ledger.get_fact("total_experience_years", category=FactCategory.WORK_EXPERIENCE)
        verified_total_exp = total_exp_fact.numeric_value if total_exp_fact else 0.0

        if years_in_answer is not None and verified_total_exp is not None:
            if years_in_answer > (verified_total_exp + 0.5):
                return VerificationResult(
                    is_valid=False,
                    requires_human_review=True,
                    confidence=0.9,
                    evidence_fact=total_exp_fact,
                    reason=f"Proposed answer claims {years_in_answer} years, exceeding candidate's total verified experience of {verified_total_exp} years",
                    suggested_answer=f"I have {verified_total_exp:g} years of relevant experience.",
                )

        if years_in_question is not None and verified_total_exp is not None:
            if years_in_question > verified_total_exp and "yes" in ans_lower:
                return VerificationResult(
                    is_valid=False,
                    requires_human_review=True,
                    confidence=0.85,
                    evidence_fact=total_exp_fact,
                    reason=f"Question requires {years_in_question} years, but candidate only has {verified_total_exp} verified years",
                    suggested_answer=f"No, but I have {verified_total_exp:g} years of focused experience.",
                )

        # 3. Specific Skill Verification
        # Check if question asks about specific skill experience
        skills = self.ledger.get_facts_by_category(FactCategory.TECHNICAL_SKILL)
        known_skill_names = [s.subject.lower() for s in skills]

        # Look for named technology keywords in question
        for skill_fact in skills:
            skill_name = skill_fact.subject.lower()
            if len(skill_name) >= 3 and skill_name in q_lower:
                # Skill is present in candidate ledger
                return VerificationResult(
                    is_valid=True,
                    requires_human_review=False,
                    confidence=0.95,
                    evidence_fact=skill_fact,
                    reason=f"Skill '{skill_fact.subject}' verified from resume fact ledger",
                )

        # 4. Unknown Question with no fact evidence
        # If the answer makes confident positive assertions for unmentioned tools
        if ("yes" in ans_lower or "expert" in ans_lower or "extensive" in ans_lower) and len(proposed_answer.split()) > 4:
            # Check if any tech term in question is completely missing from candidate skills
            potential_terms = [w for w in re.findall(r"[A-Za-z\+\#]{3,}", question) if w.lower() not in [
                "experience", "years", "have", "with", "using", "work", "role", "position", "applicant"
            ]]
            missing_terms = [t for t in potential_terms if t.lower() not in known_skill_names and t.lower() not in q_lower[:10]]
            if len(missing_terms) > 2:
                return VerificationResult(
                    is_valid=False,
                    requires_human_review=True,
                    confidence=0.7,
                    reason=f"Answer asserts positive experience with technologies not found in fact ledger ({', '.join(missing_terms[:3])})",
                )

        return VerificationResult(is_valid=True, requires_human_review=False, confidence=0.85)

    def _extract_years(self, text: str) -> Optional[float]:
        """Extracts numerical years of experience mentioned in text."""
        # e.g., "5 years", "3.5 yrs", "5+ years", "10 years"
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years?|yrs?)", text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None
