"""
Helper utilities and safety engine components for the Naukri automation platform.
Governed by the core principle: When uncertain, do not apply.
"""

from enum import Enum
import re
import urllib.parse
from typing import Optional, List, Any
from pydantic import BaseModel
from playwright.async_api import ElementHandle, Page
from app.core.logger import logger


class ApplicationType(str, Enum):
    QUICK_APPLY = "quick_apply"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


class ApplicationLimitDetected(Exception):
    """Raised when Naukri indicates applications cannot proceed for this session."""
    def __init__(self, reason: str = "Naukri application limit detected"):
        self.reason = reason
        super().__init__(reason)


def normalize_token(text: str) -> str:
    """
    Normalizes text for robust comparisons:
    lowercases, removes punctuation/extra whitespace, and standardizes hyphens to spaces.
    E.g. '30-day' -> '30 day', '30 Days ' -> '30 day'.
    """
    if not text:
        return ""
    cleaned = text.strip().lower()
    # Replace hyphens and underscores with spaces
    cleaned = re.sub(r"[-_]+", " ", cleaned)
    # Remove non-alphanumeric characters except spaces
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    # Collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def build_naukri_search_url(base_url: str, freshness_days: Optional[int] = None) -> str:
    """
    Constructs a Naukri search URL while preserving all existing query parameters.
    Appends or updates 'jobAge' if freshness_days is provided; removes 'jobAge' if None.
    """
    url_parts = list(urllib.parse.urlparse(base_url))
    query = dict(urllib.parse.parse_qsl(url_parts[4]))
    if freshness_days is not None:
        query["jobAge"] = str(freshness_days)
    elif "jobAge" in query:
        del query["jobAge"]
    url_parts[4] = urllib.parse.urlencode(query)
    return urllib.parse.urlunparse(url_parts)


async def classify_application(card_elem: ElementHandle) -> ApplicationType:
    """
    Classifies a Naukri job card based on visible text and HTML indicators.
    
    Precedence Rule:
      1. Strong external indicator -> EXTERNAL
      2. Else strong Quick Apply indicator -> QUICK_APPLY
      3. Else -> UNKNOWN
      
    Conflict resolution: If both indicators exist, EXTERNAL wins (conservative fail-safe).
    """
    try:
        card_text = (await card_elem.inner_text()).lower()
        card_html = (await card_elem.inner_html()).lower()
    except Exception as e:
        logger.debug(f"Failed to read card elements for classification: {e}")
        return ApplicationType.UNKNOWN

    # Strong external indicators
    has_external = False
    external_phrases = [
        "company site",
        "apply on company site",
        "redirect",
        "external site",
        "apply on website",
    ]
    for phrase in external_phrases:
        if phrase in card_text:
            has_external = True
            break
            
    if not has_external:
        # Check for external link classes, icons, or attributes
        if any(cls in card_html for cls in ["external-apply", "company-apply", "icon-external", "redirect"]):
            has_external = True

    # Strong quick apply indicators
    has_quick_apply = False
    quick_apply_phrases = [
        "apply directly",
        "quick apply",
        "1-click apply",
        "easy apply",
    ]
    for phrase in quick_apply_phrases:
        if phrase in card_text:
            has_quick_apply = True
            break

    if not has_quick_apply:
        # On Naukri, native cards often have an 'Apply' button or 'already applied' or standard tuple
        # But verify it's not marked external
        has_apply_btn = await card_elem.query_selector("button:has-text('Apply'), a:has-text('Apply'), .apply-button")
        if has_apply_btn and not has_external:
            has_quick_apply = True

    # Precedence & Conflict Resolution
    if has_external:
        return ApplicationType.EXTERNAL
    if has_quick_apply:
        return ApplicationType.QUICK_APPLY

    return ApplicationType.UNKNOWN


async def detect_application_limit(page: Page) -> Optional[str]:
    """
    Inspects page/modal/toast for rate limits, daily quotas, or anti-abuse banners.
    Returns the limit reason string if detected, otherwise None.
    """
    limit_indicators = [
        ("daily application limit", "Daily job application limit reached on Naukri."),
        ("application limit", "Job application limit reached on Naukri."),
        ("daily quota", "You have reached your daily application limit on Naukri."),
        ("maximum jobs", "You have applied to the maximum number of jobs allowed for today."),
        ("daily limit", "Daily job application limit reached."),
        ("quota exceeded", "Job application quota exceeded."),
        ("too many applications", "Too many applications submitted in a short period. Rate limited."),
        ("try again tomorrow", "Application limit reached. Please try again tomorrow."),
        ("reached your limit", "Application limit reached for this session."),
    ]

    try:
        # Check modals and alert banners
        banner_selectors = [
            ".quota-exceeded",
            ".limit-reached",
            ".toaster-msg",
            ".err-msg",
            ".msg-box",
            "[role='alert']",
            ".drawer-wrapper",
            ".server-err",
        ]
        for sel in banner_selectors:
            elements = await page.query_selector_all(sel)
            for el in elements:
                if await el.is_visible():
                    txt = (await el.inner_text()).lower()
                    for keyword, reason in limit_indicators:
                        if keyword in txt:
                            return reason

        # Also inspect general body text for specific quota messages if a modal opened
        body_text = (await page.inner_text("body")).lower()
        for keyword, reason in limit_indicators:
            if keyword in body_text:
                return reason

    except Exception as e:
        logger.debug(f"Error checking application limit: {e}")

    return None


def validate_llm_answer(result: Any, displayed_options: List[str]) -> Optional[str]:
    """
    Validates LLM question response against strict schema invariants and displayed options.
    
    Invariants:
      - If status is not 'ANSWERABLE':
          selected_option MUST be None. If non-None, rejected as malformed.
      - If status == 'ANSWERABLE':
          selected_option MUST be a non-empty string.
      - selected_option MUST match one of displayed_options (case-insensitive / normalized).
      
    Returns the exact matching displayed option string if valid, otherwise None (do not click).
    """
    if not isinstance(result, dict):
        return None

    status = result.get("status")
    selected_option = result.get("selected_option")

    # Invariant: UNANSWERABLE or AMBIGUOUS must not propose an option
    if status in ("UNANSWERABLE", "AMBIGUOUS"):
        if selected_option is not None:
            logger.warning(f"Malformed LLM response: status '{status}' returned non-null option '{selected_option}'. Rejecting.")
        return None

    if status != "ANSWERABLE":
        return None

    # Invariant: ANSWERABLE must provide a non-empty string
    if not selected_option or not isinstance(selected_option, str) or not selected_option.strip():
        logger.warning("Malformed LLM response: status 'ANSWERABLE' returned empty or null option. Rejecting.")
        return None

    norm_selected = normalize_token(selected_option)

    for option in displayed_options:
        if normalize_token(option) == norm_selected:
            return option

    logger.warning(
        f"LLM-selected option '{selected_option}' did not match any displayed options: {displayed_options}. Rejecting."
    )
    return None


class JobContact(BaseModel):
    email: str
    name: Optional[str] = None
    contact_type: str = "unknown"  # hr, recruiter, careers, jobs, personal, unknown
    source: str = "job_description"  # job_description, recruiter_widget
    confidence: str = "medium"  # high, medium, low


def extract_job_contacts(jd_text: str, recruiter_text: Optional[str] = None) -> List[JobContact]:
    """
    Extracts all valid contact emails from the JD and recruiter widgets.
    - Matches: hr@, recruiter@, careers@, hiring@, jobs@, and personal name emails (e.g. priya.sharma@...).
    - Filters: support@, noreply@, no-reply@, donotreply@, privacy@, legal@, security@, help@, @naukri.com, @example.com.
    - Deduplicates by lowercase email while preserving extraction source and classification.
    """
    contacts: List[JobContact] = []
    seen_emails = set()

    excluded_prefixes = (
        "support", "noreply", "no-reply", "donotreply", "do-not-reply",
        "privacy", "legal", "security", "help", "info", "admin", "contact",
        "feedback", "billing", "alert", "notification"
    )
    excluded_domains = (
        "naukri.com", "example.com", "test.com", "sample.com", "domain.com"
    )

    email_pattern = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

    def process_email(raw_email: str, source: str, default_name: Optional[str] = None) -> Optional[JobContact]:
        email = raw_email.strip().lower().rstrip(".,;!?:")
        if not email or email in seen_emails:
            return None
        
        parts = email.split("@")
        if len(parts) != 2:
            return None
        
        prefix, domain = parts
        if any(prefix.startswith(bad) or prefix == bad for bad in excluded_prefixes):
            return None
        if any(domain.endswith(bad) or domain == bad for bad in excluded_domains):
            return None
        
        # Determine contact type
        if "hr" in prefix or "talent" in prefix:
            c_type = "hr"
        elif "recruiter" in prefix or "hiring" in prefix:
            c_type = "recruiter"
        elif "career" in prefix:
            c_type = "careers"
        elif "job" in prefix:
            c_type = "jobs"
        elif "." in prefix or "_" in prefix:
            c_type = "personal"
        else:
            c_type = "unknown"

        # Determine confidence
        if source == "recruiter_widget" or default_name:
            conf = "high"
        elif c_type in ("hr", "recruiter", "careers", "jobs"):
            conf = "medium"
        else:
            conf = "low"

        seen_emails.add(email)
        return JobContact(
            email=email,
            name=default_name,
            contact_type=c_type,
            source=source,
            confidence=conf
        )

    # 1. Inspect recruiter widget text if available
    recruiter_name = None
    if recruiter_text:
        name_match = re.search(r"(?:posted\s+by|recruiter)\s*:?\s*([A-Za-z\s]{2,30})", recruiter_text, re.IGNORECASE)
        if name_match:
            recruiter_name = name_match.group(1).strip()
            recruiter_name = re.sub(r"\s*\(.*$", "", recruiter_name).strip()
            recruiter_name = re.sub(r"\s+(?:at|hiring|from|for).*$", "", recruiter_name, flags=re.IGNORECASE).strip()

        for match in email_pattern.finditer(recruiter_text):
            contact = process_email(match.group(0), source="recruiter_widget", default_name=recruiter_name)
            if contact:
                contacts.append(contact)

    # 2. Inspect job description text
    if jd_text:
        for match in email_pattern.finditer(jd_text):
            contact = process_email(match.group(0), source="job_description", default_name=recruiter_name)
            if contact:
                contacts.append(contact)

    return contacts

