"""
Universal Recruiter Contact Extractor.

Extracts recruiter emails, phone numbers, WhatsApp-compatible numbers,
recruiter names, and LinkedIn profiles from job descriptions and platform widgets.
"""

import re
from typing import List, Optional, Tuple, Dict, Any
from app.models.job import RecruiterContact
from app.platforms.naukri_helpers import extract_job_contacts, JobContact


# International and Indian mobile phone regex
PHONE_PATTERNS = [
    # Indian mobile: +91 9876543210, +91-9876543210, 09876543210, 9876543210 (starts with 6-9)
    re.compile(r"(?:(?:\+?91[\s\-]?)?|0?)([6-9]\d{4}[\s\-]?\d{5})\b"),
    # US/Canada: +1 (555) 123-4567, 555-123-4567
    re.compile(r"(?:\+?1[\s\-.]?)?(?:\(?([2-9]\d{2})\)?[\s\-.]?)?([2-9]\d{2})[\s\-.]([0-9]{4})\b"),
    # Generic international: +44 7911 123456
    re.compile(r"\+(\d{1,3})[\s\-.]?\(?(\d{2,4})\)?[\s\-.]?(\d{3,4})[\s\-.]?(\d{3,4})\b")
]

# Patterns for recruiter names
RECRUITER_NAME_PATTERNS = [
    re.compile(r"(?:posted\s+by|recruiter|contact\s+person|hiring\s+manager|talent\s+partner)\s*[:\-]\s*([A-Za-z\s.]{2,35})", re.IGNORECASE),
    re.compile(r"(?:reach\s+out\s+to|connect\s+with|write\s+to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})", re.IGNORECASE),
]

# Recruiter LinkedIn profile regex
LINKEDIN_PROFILE_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/([a-zA-Z0-9\-_%]+)/?",
    re.IGNORECASE
)


class ContactExtractorService:
    """Universal contact and recruiter intelligence extraction service."""

    def __init__(self):
        pass

    def extract_contacts(
        self,
        jd_text: str,
        recruiter_text: Optional[str] = None,
        company: Optional[str] = None
    ) -> List[RecruiterContact]:
        """
        Extract recruiter contacts combining email extraction, phone detection,
        and recruiter name/LinkedIn association.
        """
        results: List[RecruiterContact] = []
        combined_text = f"{recruiter_text or ''}\n{jd_text or ''}"

        # 1. Extract base email contacts using proven naukri_helpers logic
        base_contacts: List[JobContact] = extract_job_contacts(jd_text, recruiter_text)
        
        # 2. Extract phones and WhatsApp numbers
        phones = self.extract_phone_numbers(combined_text)
        primary_phone = phones[0] if phones else None
        
        # 3. Extract recruiter name
        recruiter_name = self.extract_recruiter_name(combined_text)
        
        # 4. Extract LinkedIn profile
        linkedin_url = self.extract_linkedin_url(combined_text)

        # Merge extracted email contacts into RecruiterContact models
        seen_identifiers = set()
        for bc in base_contacts:
            contact_name = bc.name or recruiter_name
            rc = RecruiterContact(
                name=contact_name,
                email=bc.email,
                phone=primary_phone[0] if primary_phone else None,
                whatsapp_number=primary_phone[1] if primary_phone else None,
                contact_type=bc.contact_type,
                source=bc.source,
                confidence=bc.confidence,
                company=company,
                linkedin_url=linkedin_url
            )
            seen_identifiers.add(bc.email)
            results.append(rc)

        # If phone was found but no email contact existed
        if primary_phone and not results:
            rc = RecruiterContact(
                name=recruiter_name,
                email=None,
                phone=primary_phone[0],
                whatsapp_number=primary_phone[1],
                contact_type="recruiter" if recruiter_name else "unknown",
                source="recruiter_widget" if recruiter_text else "job_description",
                confidence="medium" if recruiter_name else "low",
                company=company,
                linkedin_url=linkedin_url
            )
            results.append(rc)

        # If recruiter name or LinkedIn was found with no emails
        elif (recruiter_name or linkedin_url) and not results:
            rc = RecruiterContact(
                name=recruiter_name,
                email=None,
                phone=None,
                whatsapp_number=None,
                contact_type="recruiter",
                source="recruiter_widget" if recruiter_text else "job_description",
                confidence="low",
                company=company,
                linkedin_url=linkedin_url
            )
            results.append(rc)

        return results

    def extract_phone_numbers(self, text: str) -> List[Tuple[str, str]]:
        """
        Extracts valid mobile/phone numbers from text.
        Returns a list of tuples: (formatted_display_phone, e164_whatsapp_number).
        E.g. ('+91 9876543210', '919876543210').
        """
        if not text:
            return []

        phone_results: List[Tuple[str, str]] = []
        seen = set()

        # 1. Match Indian mobile numbers
        ind_matches = re.finditer(r"(?:(?:\+?91[\s\-]?)?|0?)([6-9]\d{4}[\s\-]?\d{5})\b", text)
        for m in ind_matches:
            raw_digits = re.sub(r"\D", "", m.group(0))
            # Normalize to 10 digits
            if len(raw_digits) == 12 and raw_digits.startswith("91"):
                ten_digit = raw_digits[2:]
            elif len(raw_digits) == 11 and raw_digits.startswith("0"):
                ten_digit = raw_digits[1:]
            elif len(raw_digits) == 10:
                ten_digit = raw_digits
            else:
                continue

            if ten_digit[0] in "6789":
                e164 = f"91{ten_digit}"
                display = f"+91 {ten_digit[:5]} {ten_digit[5:]}"
                if e164 not in seen:
                    seen.add(e164)
                    phone_results.append((display, e164))

        # 2. Match US/International numbers if no Indian numbers found or in addition
        if not phone_results:
            us_matches = re.finditer(r"\+?1[\s\-.]?\(?([2-9]\d{2})\)?[\s\-.]?([2-9]\d{2})[\s\-.]([0-9]{4})\b", text)
            for m in us_matches:
                raw_digits = re.sub(r"\D", "", m.group(0))
                if len(raw_digits) == 11 and raw_digits.startswith("1"):
                    e164 = raw_digits
                    display = f"+1 ({raw_digits[1:4]}) {raw_digits[4:7]}-{raw_digits[7:]}"
                    if e164 not in seen:
                        seen.add(e164)
                        phone_results.append((display, e164))

        return phone_results

    def extract_recruiter_name(self, text: str) -> Optional[str]:
        """Extract candidate recruiter name from text."""
        if not text:
            return None

        for pattern in RECRUITER_NAME_PATTERNS:
            match = pattern.search(text)
            if match:
                raw_name = match.group(1).strip()
                # Clean up parentheticals or roles
                cleaned = re.sub(r"\(.*?\)", "", raw_name)
                cleaned = re.sub(r"\s+(?:at|from|for|hiring|recruiting).*$", "", cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r"[^\w\s.]", "", cleaned).strip()
                if 2 <= len(cleaned) <= 35 and not any(ch.isdigit() for ch in cleaned):
                    # Avoid generic words
                    if cleaned.lower() not in ["hr team", "hiring team", "recruiter", "talent acquisition"]:
                        return cleaned
        return None

    def extract_linkedin_url(self, text: str) -> Optional[str]:
        """Extract recruiter LinkedIn URL from text."""
        if not text:
            return None
        match = LINKEDIN_PROFILE_PATTERN.search(text)
        if match:
            slug = match.group(1).strip()
            return f"https://www.linkedin.com/in/{slug}"
        return None

    def get_primary_contact(self, contacts: List[RecruiterContact]) -> Optional[RecruiterContact]:
        """Select best contact prioritizing direct HR/recruiter emails with names."""
        if not contacts:
            return None

        # Prioritize: has email and name, then high confidence, then has email
        def score_contact(c: RecruiterContact) -> int:
            score = 0
            if c.email:
                score += 50
            if c.name:
                score += 30
            if c.confidence == "high":
                score += 20
            elif c.confidence == "medium":
                score += 10
            if c.contact_type in ["hr", "recruiter", "hiring_manager"]:
                score += 15
            if c.whatsapp_number:
                score += 5
            return score

        return max(contacts, key=score_contact)


contact_extractor_service = ContactExtractorService()
