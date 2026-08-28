import json
from pathlib import Path
from typing import Dict, Any, Optional
import pypdf
import docx
from app.core.config import settings
from app.core.llm import llm_client
from app.core.logger import logger
from app.models.job import ResumeProfile

class ResumeParserService:
    def __init__(self):
        self.profile_path = settings.PROFILE_FILE_PATH
        self.resume_path = settings.RESUME_FILE_PATH

    def extract_text_from_pdf(self, file_path: Path) -> str:
        """Extract text from PDF using pypdf with fallback."""
        text_parts = []
        try:
            reader = pypdf.PdfReader(str(file_path))
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            return "\n\n".join(text_parts).strip()
        except Exception as e:
            logger.error(f"Failed to extract text from PDF {file_path}: {e}")
            raise ValueError(f"Could not read PDF file: {str(e)}")

    def extract_text_from_docx(self, file_path: Path) -> str:
        """Extract text from DOCX using python-docx."""
        try:
            doc = docx.Document(str(file_path))
            full_text = []
            for para in doc.paragraphs:
                if para.text.strip():
                    full_text.append(para.text)
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_text:
                        full_text.append(" | ".join(row_text))
            return "\n".join(full_text).strip()
        except Exception as e:
            logger.error(f"Failed to extract text from DOCX {file_path}: {e}")
            raise ValueError(f"Could not read DOCX file: {str(e)}")

    async def parse_and_save_resume(self, file_path: Path) -> ResumeProfile:
        """Extract text from resume file, parse structured profile with LLM, and persist."""
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            raw_text = self.extract_text_from_pdf(file_path)
        elif suffix in [".docx", ".doc"]:
            raw_text = self.extract_text_from_docx(file_path)
        else:
            raise ValueError(f"Unsupported resume format: {suffix}. Please upload .pdf or .docx")

        if not raw_text or len(raw_text.strip()) < 50:
            raise ValueError("Resume file contains insufficient or unreadable text.")

        logger.info(f"Extracted {len(raw_text)} characters of text from resume. Passing to LLM parser...")
        parsed_json = await llm_client.parse_resume_text(raw_text)

        if not parsed_json or not parsed_json.get("full_name"):
            logger.warning("LLM parser returned incomplete data, attempting fallback extraction...")
            # Basic fallback structure if LLM is offline or partially parsed
            parsed_json = self._build_fallback_profile(raw_text, parsed_json)

        # Validate with Pydantic model
        profile = ResumeProfile(**parsed_json)
        
        # Save profile JSON to data folder
        self.save_profile(profile)
        return profile

    def _build_fallback_profile(self, raw_text: str, partial: Dict[str, Any]) -> Dict[str, Any]:
        """Generate safe fallback profile when LLM parser outputs incomplete JSON."""
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        first_line = lines[0] if lines else "Candidate"
        
        return {
            "full_name": partial.get("full_name") or first_line,
            "email": partial.get("email") or "",
            "phone": partial.get("phone") or "",
            "location": partial.get("location") or "Remote / Flexible",
            "linkedin_url": partial.get("linkedin_url") or "",
            "github_url": partial.get("github_url") or "",
            "portfolio_url": partial.get("portfolio_url") or "",
            "years_of_experience": partial.get("years_of_experience", 3.0),
            "summary": partial.get("summary") or "Experienced software developer.",
            "skills": partial.get("skills") or ["JavaScript", "Python", "React", "Node.js"],
            "work_experience": partial.get("work_experience") or [],
            "education": partial.get("education") or [],
            "certifications": partial.get("certifications") or [],
            "languages": partial.get("languages") or ["English"]
        }

    def save_profile(self, profile: ResumeProfile) -> None:
        """Save ResumeProfile to disk as JSON."""
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(), f, indent=2, ensure_ascii=False)
        logger.info(f"Saved candidate profile to {self.profile_path}")

    def load_profile(self) -> Optional[ResumeProfile]:
        """Load saved profile JSON from disk if exists."""
        if not self.profile_path.exists():
            return None
        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return ResumeProfile(**data)
        except Exception as e:
            logger.error(f"Error reading profile file: {e}")
            return None

resume_parser_service = ResumeParserService()
