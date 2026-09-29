"""
Smart Form-Filling Intelligence & Semantic Dropdown Resolver.
Provides robust resolution of diverse ATS form fields, fuzzy option matching,
dynamic salary target calculation, and multi-step portal navigation heuristics.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.core.logger import logger


class ResolvedField(BaseModel):
    selected_option: str
    confidence: float
    canonical_category: str
    reasoning: str


class SalaryRecommendation(BaseModel):
    recommended_salary: float
    currency: str
    extracted_range: Optional[Tuple[float, float]] = None
    strategy_applied: str


class FormIntelligenceService:
    """
    Intelligent field resolution engine for job application portals.
    Maps arbitrary portal questions and options to verified candidate profiles.
    """

    # Canonical semantic categories and synonym triggers
    CATEGORY_SYNONYMS = {
        "work_authorization": [
            "authorized to work", "legally authorized", "work authorization", 
            "eligible to work", "right to work", "visa status"
        ],
        "visa_sponsorship": [
            "require sponsorship", "sponsorship now or in the future", "visa sponsorship", 
            "need sponsorship", "require visa", "immigration sponsorship"
        ],
        "notice_period": [
            "notice period", "how soon can you start", "how soon can you join", 
            "how soon", "availability to start", "start date", "joining period", 
            "when can you start", "when can you join", "soon can you"
        ],
        "relocation": [
            "willing to relocate", "open to relocation", "relocate", 
            "relocation assistance", "willing to move"
        ],
        "clearance": [
            "security clearance", "active clearance", "security clearance status"
        ],
        "gender": [
            "gender", "sex", "gender identity"
        ],
        "race_ethnicity": [
            "race", "ethnicity", "ethnic origin", "demographic"
        ],
        "veteran_status": [
            "veteran status", "military service", "protected veteran"
        ],
        "disability_status": [
            "disability", "differently abled", "physical impairment"
        ]
    }

    NAVIGATION_BUTTON_PATTERNS = [
        r"^(next|continue|proceed|next step|review|save & continue)$",
        r"^(submit|submit application|apply now|complete application)$",
        r"^(i accept|i agree|confirm)$"
    ]

    def __init__(self):
        pass

    def classify_question_category(self, question_text: str) -> Optional[str]:
        """Classify a form question into one of the canonical categories."""
        q_norm = question_text.lower().strip()
        for cat, synonyms in self.CATEGORY_SYNONYMS.items():
            for syn in synonyms:
                if syn in q_norm:
                    return cat
        return None

    def resolve_dropdown_or_radio(
        self,
        question_text: str,
        options: List[str],
        vault_profile: Dict[str, Any],
        default_fallback: Optional[str] = None
    ) -> ResolvedField:
        """
        Resolves the optimal option from a list of options based on question semantics
        and the candidate's verified Answer Vault.
        """
        if not options:
            return ResolvedField(
                selected_option=default_fallback or "",
                confidence=0.0,
                canonical_category="unknown",
                reasoning="No options provided"
            )

        category = self.classify_question_category(question_text)
        options_norm = [opt.strip() for opt in options]

        # 1. Work Authorization (default: Yes / Authorized)
        if category == "work_authorization":
            target_authorized = vault_profile.get("work_authorized", True)
            for opt in options_norm:
                if target_authorized and re.search(r"\b(yes|authorized|eligible|citizen|permanent resident|have valid)\b", opt, re.I):
                    return ResolvedField(selected_option=opt, confidence=0.95, canonical_category=category, reasoning="Authorized candidate selection")
                if not target_authorized and re.search(r"\b(no|not authorized)\b", opt, re.I):
                    return ResolvedField(selected_option=opt, confidence=0.95, canonical_category=category, reasoning="Non-authorized candidate selection")

        # 2. Visa Sponsorship (default: No sponsorship required)
        elif category == "visa_sponsorship":
            needs_sponsorship = vault_profile.get("requires_sponsorship", False)
            for opt in options_norm:
                if not needs_sponsorship and re.search(r"\b(no|will not require|do not require|not need)\b", opt, re.I):
                    return ResolvedField(selected_option=opt, confidence=0.95, canonical_category=category, reasoning="No sponsorship required")
                if needs_sponsorship and re.search(r"\b(yes|will require|require sponsorship)\b", opt, re.I):
                    return ResolvedField(selected_option=opt, confidence=0.95, canonical_category=category, reasoning="Candidate requires sponsorship")

        # 3. Notice Period / Availability
        elif category == "notice_period":
            candidate_notice = str(vault_profile.get("notice_period_days", "30")).lower()
            # Match immediate / 15 days / 30 days
            for opt in options_norm:
                if "immediate" in candidate_notice and re.search(r"\b(immediate|0 days|available immediately)\b", opt, re.I):
                    return ResolvedField(selected_option=opt, confidence=0.90, canonical_category=category, reasoning="Matched immediate notice")
                if "15" in candidate_notice and re.search(r"\b(15 days|2 weeks|< 1 month)\b", opt, re.I):
                    return ResolvedField(selected_option=opt, confidence=0.90, canonical_category=category, reasoning="Matched 15 days notice")
                if "30" in candidate_notice and re.search(r"\b(30 days|1 month|4 weeks)\b", opt, re.I):
                    return ResolvedField(selected_option=opt, confidence=0.90, canonical_category=category, reasoning="Matched 30 days notice")

        # 4. Relocation
        elif category == "relocation":
            willing_relocate = vault_profile.get("willing_to_relocate", True)
            for opt in options_norm:
                if willing_relocate and re.search(r"\b(yes|willing|open)\b", opt, re.I):
                    return ResolvedField(selected_option=opt, confidence=0.90, canonical_category=category, reasoning="Willing to relocate")
                if not willing_relocate and re.search(r"\b(no|not willing)\b", opt, re.I):
                    return ResolvedField(selected_option=opt, confidence=0.90, canonical_category=category, reasoning="Not open to relocation")

        # 5. EEO Compliance questions (Gender / Race / Veteran / Disability) -> Defer to Decline to Self-Identify if unsure
        elif category in ("gender", "race_ethnicity", "veteran_status", "disability_status"):
            for opt in options_norm:
                if re.search(r"\b(decline to self-identify|prefer not to say|do not wish to disclose|prefer not to answer)\b", opt, re.I):
                    return ResolvedField(selected_option=opt, confidence=0.85, canonical_category=category, reasoning="Standard EEO privacy preference")

        # 6. Fallback: Fuzzy token overlap with default
        if default_fallback:
            for opt in options_norm:
                if default_fallback.lower() in opt.lower() or opt.lower() in default_fallback.lower():
                    return ResolvedField(selected_option=opt, confidence=0.75, canonical_category=category or "general", reasoning="Fuzzy matched default fallback")

        # Fallback to first non-empty option
        chosen = options_norm[0] if options_norm else ""
        return ResolvedField(selected_option=chosen, confidence=0.50, canonical_category=category or "unknown", reasoning="Default first option fallback")

    def calculate_competitive_salary(
        self,
        job_description: str,
        candidate_target: float,
        candidate_currency: str = "USD"
    ) -> SalaryRecommendation:
        """
        Extracts salary ranges from job posting text and calculates a competitive target.
        Applies 75th percentile of posted range if present, else candidate target + 10%.
        """
        # Look for USD pattern: $120,000 - $150,000 or $120k - $150k
        usd_range = re.findall(r"\$\s*([\d,]+)\s*(?:k)?\s*(?:-|to)\s*\$\s*([\d,]+)\s*(k)?", job_description, re.I)
        if usd_range:
            raw_low, raw_high, is_k = usd_range[0]
            mult = 1000.0 if (is_k or "k" in raw_low.lower() or "k" in raw_high.lower() or len(raw_low) <= 3) else 1.0
            try:
                low = float(raw_low.replace(",", "").replace("k", "")) * mult
                high = float(raw_high.replace(",", "").replace("k", "")) * mult
                if low > high:
                    low, high = high, low
                # 75th percentile target
                target = low + (high - low) * 0.75
                return SalaryRecommendation(
                    recommended_salary=round(target, 0),
                    currency="USD",
                    extracted_range=(low, high),
                    strategy_applied="75th percentile of posted USD range"
                )
            except Exception:
                pass

        # Look for INR LPA pattern: e.g. 15 - 25 LPA or 15-20 Lacs
        inr_range = re.findall(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs|lacs)", job_description, re.I)
        if inr_range:
            try:
                low = float(inr_range[0][0])
                high = float(inr_range[0][1])
                if low > high:
                    low, high = high, low
                target = low + (high - low) * 0.75
                return SalaryRecommendation(
                    recommended_salary=round(target, 1),
                    currency="INR_LPA",
                    extracted_range=(low, high),
                    strategy_applied="75th percentile of posted INR LPA range"
                )
            except Exception:
                pass

        # Default strategy: Candidate Target + 10% premium
        recommended = candidate_target * 1.10
        return SalaryRecommendation(
            recommended_salary=round(recommended, 0),
            currency=candidate_currency,
            extracted_range=None,
            strategy_applied="Candidate preferred target + 10% negotiation margin"
        )

    def is_navigation_button(self, button_text: str) -> bool:
        """Determines if a button or link triggers a progression step in multi-page ATS forms."""
        text = button_text.strip().lower()
        for pat in self.NAVIGATION_BUTTON_PATTERNS:
            if re.search(pat, text, re.I):
                return True
        return False


# Global service instance
form_intelligence = FormIntelligenceService()
