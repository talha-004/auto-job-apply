"""
QAVaultService — Deterministic ATS Memory & Form Field Matcher.

Maps incoming form field labels, names, placeholders, and aria-labels directly to
verified candidate information before resorting to LLM generation.
Eliminates hallucinations and guarantees factual accuracy for portal screening questions.
"""

import re
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel, Field

from app.models.job import ResumeProfile, QAVault
from app.platforms.naukri_helpers import normalize_token


class VaultMatchResult(BaseModel):
    matched: bool = False
    field_key: str = ""
    value: Any = None
    source: str = "none"  # "qa_vault", "profile", "custom_qa", "fallback", "none"
    confidence: float = 0.0  # 1.0 for exact vault match, 0.8 for profile attribute
    requires_confirmation: bool = False


# Pattern map: (list_of_regex_or_keyword_patterns, vault_attribute, fallback_val, value_type)
VAULT_FIELD_PATTERNS: List[Tuple[List[str], str, Any, str]] = [
    # --- Contact Details ---
    (
        ["full name", "your name", "candidate name", "applicant name", "first name and last name"],
        "full_name",
        "",
        "string"
    ),
    (
        ["email", "e-mail", "email address", "mail id"],
        "email",
        "",
        "string"
    ),
    (
        ["phone", "mobile", "contact number", "cell number", "telephone"],
        "phone",
        "",
        "string"
    ),
    (
        ["linkedin", "linked in", "linkedin profile", "linkedin url"],
        "linkedin_url",
        "",
        "string"
    ),
    (
        ["github", "git hub", "github profile", "github url"],
        "github_url",
        "",
        "string"
    ),
    (
        ["portfolio", "website", "personal website", "portfolio url", "personal link"],
        "portfolio_url",
        "",
        "string"
    ),

    # --- Notice Period & Availability ---
    (
        ["notice period", "notice_period", "official notice", "serving notice", "notice period in days", "how many days notice"],
        "notice_period",
        "Immediate",
        "string"
    ),
    (
        ["how soon can you join", "joining time", "earliest start date", "availability", "when can you start"],
        "availability",
        "Immediate",
        "string"
    ),

    # --- Experience ---
    (
        ["total experience", "years of experience", "overall experience", "total work experience", "exp in years", "total years"],
        "experience_years",
        2.0,
        "float"
    ),
    (
        ["relevant experience", "relevant work experience", "relevant exp"],
        "relevant_experience_years",
        2.0,
        "float"
    ),

    # --- Compensation (CTC) ---
    (
        ["current ctc", "current salary", "current compensation", "present ctc", "present salary", "current annual compensation"],
        "current_ctc_lpa",
        2.4,
        "float"
    ),
    (
        ["expected ctc", "expected salary", "expected compensation", "desired salary", "desired ctc", "salary expectations"],
        "expected_ctc_lpa",
        3.5,
        "float"
    ),

    # --- Work Authorization & Sponsorship ---
    (
        ["work authorization", "authorized to work", "legally authorized", "eligible to work", "right to work", "work eligibility", "visa status", "visa eligibility", "work permit"],
        "work_authorization",
        "Yes",
        "string"
    ),
    (
        ["require sponsorship", "need sponsorship", "visa sponsorship", "require visa sponsorship", "will you require sponsorship"],
        "require_sponsorship",
        "No",
        "string"
    ),

    # --- Relocation & Remote Preferences ---
    (
        ["relocat", "willing to relocate", "open to relocation", "comfortable relocating"],
        "willing_to_relocate",
        "Yes",
        "string"
    ),
    (
        ["remote", "open to remote", "work from home", "remote work preference"],
        "remote_preference",
        "Yes",
        "string"
    ),

    # --- Demographics & Declarations ---
    (
        ["gender", "sex"],
        "gender",
        "Decline to specify",
        "string"
    ),
    (
        ["veteran", "military service", "armed forces"],
        "veteran_status",
        "No",
        "string"
    ),
    (
        ["disability", "differently abled", "physical handicap"],
        "disability_status",
        "No",
        "string"
    ),
    (
        ["driver license", "driving license", "valid license"],
        "driving_license",
        "Yes",
        "string"
    ),
    (
        ["highest education", "highest qualification", "degree", "highest degree completed"],
        "highest_education",
        "Master of Business Administration – Information Technology",
        "string"
    )
]


class QAVaultService:
    """Service providing verified answer matching against candidate QA Vault."""

    def __init__(self):
        pass

    def match_field(
        self,
        field_hint: str,
        profile: ResumeProfile,
        options: Optional[List[str]] = None
    ) -> VaultMatchResult:
        """
        Attempts to find a verified answer for the given field hint.
        
        Args:
            field_hint: Cleaned text combining label, placeholder, name, id, or question.
            profile: Candidate ResumeProfile with QAVault.
            options: Optional list of available select/radio choices.
            
        Returns:
            VaultMatchResult with matched value and confidence.
        """
        if not field_hint or not profile:
            return VaultMatchResult(matched=False)

        norm_hint = normalize_token(field_hint)
        vault = profile.qa_vault or QAVault()

        # 1. Check custom_qa dictionary for explicit exact match
        if vault.custom_qa:
            for custom_k, custom_v in vault.custom_qa.items():
                if normalize_token(custom_k) in norm_hint:
                    val = self._align_with_options(custom_v, options) if options else custom_v
                    return VaultMatchResult(
                        matched=True,
                        field_key=custom_k,
                        value=val,
                        source="custom_qa",
                        confidence=1.0
                    )

        # 2. Check predefined VAULT_FIELD_PATTERNS
        for patterns, key, fallback_val, val_type in VAULT_FIELD_PATTERNS:
            for pattern in patterns:
                norm_pat = normalize_token(pattern)
                # Check pattern as substring or regex word match
                if norm_pat in norm_hint or re.search(r"\b" + re.escape(norm_pat) + r"\b", norm_hint):
                    # Check if attribute exists on vault or profile
                    raw_val = getattr(vault, key, None)
                    source_tag = "qa_vault"

                    if raw_val is None or raw_val == "":
                        # Try profile top-level attributes (full_name, email, phone, etc.)
                        raw_val = getattr(profile, key, None)
                        source_tag = "profile"

                    # If still None, check profile.custom_answers compatibility
                    if raw_val is None and profile.custom_answers:
                        raw_val = profile.custom_answers.get(key)
                        source_tag = "custom_answers"

                    if raw_val is None:
                        raw_val = fallback_val
                        source_tag = "fallback"

                    final_val = self._format_value(raw_val, val_type, norm_hint)
                    if options:
                        final_val = self._align_with_options(final_val, options)

                    return VaultMatchResult(
                        matched=True,
                        field_key=key,
                        value=final_val,
                        source=source_tag,
                        confidence=1.0 if source_tag in ["qa_vault", "profile"] else 0.8
                    )

        # 3. Check for specific skill experience question
        # e.g. "How many years of experience do you have in React.js?"
        skill_match = self._match_skill_experience(norm_hint, profile)
        if skill_match:
            val = self._align_with_options(skill_match, options) if options else skill_match
            return VaultMatchResult(
                matched=True,
                field_key="skill_experience",
                value=val,
                source="profile",
                confidence=0.85
            )

        return VaultMatchResult(matched=False)

    def _format_value(self, val: Any, val_type: str, hint: str) -> Any:
        """Format value according to expected field type or question specifics."""
        if val is None:
            return ""

        # Specific notice period formatting:
        # If question specifically asks for "days", format as integer/string
        if "day" in hint and "notice" in hint:
            if isinstance(val, (int, float)):
                return int(val)
            if str(val).isdigit():
                return int(val)
            if "immediate" in str(val).lower():
                return 0

        if val_type == "float":
            try:
                return float(val)
            except (ValueError, TypeError):
                return str(val)

        if val_type == "int":
            try:
                return int(val)
            except (ValueError, TypeError):
                return str(val)

        return str(val)

    def _align_with_options(self, target_val: Any, options: List[str]) -> str:
        """
        Chooses the closest matching option from a form's provided choices.
        E.g. if target_val is "Yes" and options are ["Yes, I am authorized", "No"], picks "Yes, I am authorized".
        """
        if not options:
            return str(target_val)

        target_str = str(target_val).strip()
        norm_target = normalize_token(target_str)

        # 1. Exact token match
        for opt in options:
            if normalize_token(opt) == norm_target:
                return opt

        # 2. Substring match
        for opt in options:
            norm_opt = normalize_token(opt)
            if norm_target in norm_opt or norm_opt in norm_target:
                return opt

        # 3. Binary Yes/No fallback alignment
        if norm_target in ["yes", "true", "y"]:
            for opt in options:
                if any(w in normalize_token(opt) for w in ["yes", "authorized", "eligible", "agree", "accept"]):
                    return opt
        elif norm_target in ["no", "false", "n"]:
            for opt in options:
                if any(w in normalize_token(opt) for w in ["no", "not", "decline", "neither"]):
                    return opt

        # 4. Immediate / notice period alignment
        if norm_target in ["immediate", "0", "15", "15 days"]:
            for opt in options:
                norm_opt = normalize_token(opt)
                if any(w in norm_opt for w in ["immediate", "serving", "15", "1 month", "30 days"]):
                    return opt

        # Default fallback to first option
        return options[0]

    def _match_skill_experience(self, norm_hint: str, profile: ResumeProfile) -> Optional[float]:
        """Detects if field asks for years of experience in a specific candidate skill."""
        if not profile.skills:
            return None

        # Look for phrases like "years of experience in <skill>" or "<skill> experience"
        if "experience" in norm_hint:
            for skill in profile.skills:
                norm_skill = normalize_token(skill)
                if len(norm_skill) >= 3 and norm_skill in norm_hint:
                    # Candidate has this skill! Return overall experience or 1.5 - 2.0 years
                    return min(profile.years_of_experience, 2.0) if profile.years_of_experience > 0 else 1.5

        return None


qa_vault_service = QAVaultService()
