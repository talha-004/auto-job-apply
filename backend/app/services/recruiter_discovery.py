"""
Recruiter Lead Discovery Engine.
Discovers relevant hiring leads, engineering managers, and technical recruiters
for target companies, deriving corporate email address formats with confidence scoring.
"""

import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class RecruiterLead(BaseModel):
    name: str
    title: str
    company: str
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    confidence: str = "medium"  # high, medium, low
    source: str = "job_posting_discovery"


class RecruiterDiscoveryService:
    """
    Identifies recruiters and hiring managers from job descriptions,
    company domain names, and standard enterprise naming conventions.
    """

    KNOWN_COMPANY_DOMAINS = {
        "google": "google.com",
        "amazon": "amazon.com",
        "microsoft": "microsoft.com",
        "meta": "meta.com",
        "apple": "apple.com",
        "netflix": "netflix.com",
        "stripe": "stripe.com",
        "uber": "uber.com",
        "airbnb": "airbnb.com"
    }

    EMAIL_PATTERNS = [
        "{first}.{last}@{domain}",
        "{first}@{domain}",
        "{first}{last}@{domain}",
        "{f}{last}@{domain}"
    ]

    def __init__(self):
        pass

    def extract_recruiter_from_text(self, text: str, company_name: str) -> Optional[RecruiterLead]:
        """Scans job description text for explicit recruiter mentions and contact emails."""
        # 1. Look for explicit recruiter email in text
        email_match = re.search(r"[\w\.-]+@([\w\.-]+\.\w+)", text)
        found_email = email_match.group(0) if email_match else None

        # 2. Look for explicit recruiter name mentions
        name_match = re.search(
            r"(?:posted by|recruiter|hiring manager|contact|reach out to)\s*[:\-]?\s*([A-Z][a-z]+ [A-Z][a-z]+)",
            text,
            re.I
        )
        recruiter_name = name_match.group(1) if name_match else None

        if recruiter_name or found_email:
            return RecruiterLead(
                name=recruiter_name or "Talent Acquisition Team",
                title=f"Technical Recruiter at {company_name}",
                company=company_name,
                email=found_email,
                confidence="high" if found_email else "medium",
                source="posting_text_extraction"
            )

        return None

    def derive_corporate_email(self, first_name: str, last_name: str, company: str) -> str:
        """Derives a candidate corporate email address based on company domain patterns."""
        clean_first = re.sub(r"[^a-zA-Z]", "", first_name).lower()
        clean_last = re.sub(r"[^a-zA-Z]", "", last_name).lower()
        clean_co = re.sub(r"[^a-zA-Z0-9]", "", company).lower()

        domain = self.KNOWN_COMPANY_DOMAINS.get(clean_co, f"{clean_co}.com")
        return f"{clean_first}.{clean_last}@{domain}"

    def discover_leads_for_company(self, company: str, target_role: str) -> List[RecruiterLead]:
        """Generates targeted outreach leads for a given company and role."""
        clean_company = company.strip()
        domain = self.KNOWN_COMPANY_DOMAINS.get(clean_company.lower(), f"{re.sub(r'[^a-zA-Z0-9]', '', clean_company).lower()}.com")

        # Typical lead templates
        leads = [
            RecruiterLead(
                name="Talent Acquisition Team",
                title=f"Technical Recruiting Lead at {clean_company}",
                company=clean_company,
                email=f"careers@{domain}",
                confidence="high",
                source="domain_resolution"
            ),
            RecruiterLead(
                name="Engineering Hiring Team",
                title=f"Engineering Manager at {clean_company}",
                company=clean_company,
                email=f"engineering.jobs@{domain}",
                confidence="medium",
                source="domain_resolution"
            )
        ]
        return leads


# Global service instance
recruiter_discovery = RecruiterDiscoveryService()
