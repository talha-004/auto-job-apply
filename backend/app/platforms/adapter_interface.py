"""
Standard ApplicationAdapter Interface.
Defines the unified lifecycle contract for job application automation across both
portal platforms (LinkedIn, Naukri, Indeed) and external ATS systems (Greenhouse, Lever).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple, List
from pydantic import BaseModel, Field

from app.models.job import (
    ResumeProfile,
    QAVault,
    ApplicationStatus,
    ReasonCode,
)


class AdapterApplicationResult(BaseModel):
    """Normalized outcome of an application attempt through an ApplicationAdapter."""
    success: bool
    status: ApplicationStatus
    job_url: str
    job_title: str = ""
    company: str = ""
    reason_code: Optional[ReasonCode] = None
    message: str = ""
    attempt_id: Optional[str] = None
    confirmation_evidence: Optional[str] = None
    filled_fields: Dict[str, Any] = Field(default_factory=dict)
    unfilled_fields: List[str] = Field(default_factory=list)


class ApplicationAdapter(ABC):
    """
    Standard interface for all job application automation adapters.
    Methods:
      - detect: Determines whether this adapter handles the target URL or page
      - authenticate: Validates sessions, credentials, or cookies
      - extract_form: Parses input fields, dropdowns, and file upload targets
      - fill_form: Populates form fields with profile and QA Vault data
      - submit: Executes submission action
      - verify_submission: Validates whether application succeeded, failed, or requires review
      - apply: Orchestrates the entire application flow for a single job
    """

    @abstractmethod
    def detect(self, url: str, page_content: Optional[str] = None) -> bool:
        """Return True if this adapter can process the given job URL or page content."""
        pass

    @abstractmethod
    async def authenticate(self) -> bool:
        """Validate or establish authentication/session on the platform/board."""
        pass

    @abstractmethod
    async def extract_form(self, page: Any) -> Dict[str, Any]:
        """Extract all visible and interactable form fields from the application page."""
        pass

    @abstractmethod
    async def fill_form(
        self,
        page: Any,
        profile: ResumeProfile,
        qa_vault: Optional[QAVault] = None
    ) -> Dict[str, Any]:
        """Fill all extracted fields using candidate profile and smart QA Vault."""
        pass

    @abstractmethod
    async def submit(self, page: Any) -> bool:
        """Click the final submission button safely."""
        pass

    @abstractmethod
    async def verify_submission(self, page: Any) -> Tuple[bool, str]:
        """Verify whether application was successfully submitted or failed."""
        pass

    @abstractmethod
    async def apply(
        self,
        job_url: str,
        profile: ResumeProfile,
        qa_vault: Optional[QAVault] = None
    ) -> AdapterApplicationResult:
        """Execute end-to-end application workflow for the specified job URL."""
        pass
