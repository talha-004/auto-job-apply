import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logger import broadcaster, LogLevel
from app.models.job import ResumeProfile, QAVault
from app.services.resume_parser import resume_parser_service
from app.services.resume_tailorer import resume_tailorer, TailoredResumeResult

router = APIRouter()

class TailorResumeRequest(BaseModel):
    job_title: str = Field(..., min_length=2)
    job_description: str = Field(..., min_length=10)
    job_id: Optional[str] = None

@router.post("/upload")
async def upload_resume(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Upload a candidate resume (.pdf or .docx) and parse into structured profile using local LLM."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in [".pdf", ".docx", ".doc"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload a PDF (.pdf) or Word document (.docx)."
        )

    # Save uploaded file locally
    target_path = settings.DATA_PATH / f"uploaded_resume{suffix}"
    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Also copy as standard current_resume.pdf or matching extension
        saved_resume_path = settings.RESUME_FILE_PATH
        with open(saved_resume_path, "wb") as buffer:
            file.file.seek(0)
            shutil.copyfileobj(file.file, buffer)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    await broadcaster.emit_log(f"📄 Resume file '{file.filename}' uploaded. Parsing with Ollama...", level=LogLevel.INFO)

    try:
        profile = await resume_parser_service.parse_and_save_resume(target_path)
        await broadcaster.emit_log(
            f"✅ Resume successfully parsed for: {profile.full_name} ({len(profile.skills)} skills extracted)",
            level=LogLevel.SUCCESS
        )
        return {
            "success": True,
            "filename": file.filename,
            "profile": profile
        }
    except Exception as e:
        await broadcaster.emit_log(f"⚠️ Error parsing resume: {str(e)}", level=LogLevel.ERROR)
        raise HTTPException(status_code=500, detail=f"Failed to parse resume: {str(e)}")

@router.get("/profile")
async def get_profile() -> Dict[str, Any]:
    """Get the currently loaded candidate profile."""
    profile = resume_parser_service.load_profile()
    return {
        "exists": profile is not None,
        "profile": profile
    }

@router.put("/profile")
async def update_profile(profile: ResumeProfile) -> Dict[str, Any]:
    """Manually update or fine-tune candidate profile fields."""
    try:
        resume_parser_service.save_profile(profile)
        await broadcaster.emit_log(f"Profile updated for {profile.full_name}.", level=LogLevel.INFO)
        return {
            "success": True,
            "profile": profile
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save profile: {str(e)}")

@router.get("/vault")
async def get_qa_vault() -> Dict[str, Any]:
    """Get the candidate QA Vault knowledge base."""
    profile = resume_parser_service.load_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="No candidate profile found. Please upload a resume first.")
    return {
        "success": True,
        "vault": profile.qa_vault
    }

@router.put("/vault")
async def update_qa_vault(vault: QAVault) -> Dict[str, Any]:
    """Update candidate QA Vault fields."""
    profile = resume_parser_service.load_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="No candidate profile found. Please upload a resume first.")
    try:
        profile.qa_vault = vault
        # Keep custom_answers synchronized for backwards compatibility
        profile.custom_answers["notice_period_days"] = vault.notice_period_days
        profile.custom_answers["expected_salary"] = f"{vault.expected_ctc_lpa} LPA" if vault.expected_ctc_lpa else "Negotiable"
        profile.custom_answers["current_salary"] = f"{vault.current_ctc_lpa} LPA" if vault.current_ctc_lpa else ""
        profile.custom_answers["work_authorization"] = vault.work_authorization
        profile.custom_answers["require_sponsorship"] = vault.require_sponsorship
        profile.custom_answers["willing_to_relocate"] = vault.willing_to_relocate
        profile.custom_answers["remote_preferred"] = vault.remote_preference
        profile.custom_answers["gender"] = vault.gender
        profile.custom_answers["veteran_status"] = vault.veteran_status
        profile.custom_answers["disability_status"] = vault.disability_status

        resume_parser_service.save_profile(profile)
        await broadcaster.emit_log("Candidate QA Vault updated successfully.", level=LogLevel.INFO)
        return {
            "success": True,
            "vault": profile.qa_vault
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not update QA Vault: {str(e)}")

@router.post("/tailor", response_model=TailoredResumeResult)
async def tailor_resume_endpoint(req: TailorResumeRequest) -> TailoredResumeResult:
    """Generate an ATS-tailored PDF resume aligned with the target job description."""
    profile = resume_parser_service.load_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="No candidate profile found. Please upload a resume first.")

    try:
        res = resume_tailorer.generate_tailored_resume(
            profile=profile,
            job_title=req.job_title,
            jd_text=req.job_description,
            job_id=req.job_id
        )
        await broadcaster.emit_log(
            f"📄 Tailored resume generated for '{req.job_title}' ({res.file_size_bytes} bytes).",
            level=LogLevel.SUCCESS
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate tailored resume: {str(e)}")

@router.get("/tailored/{job_id}/download")
async def download_tailored_resume(job_id: str):
    """Download the tailored PDF resume for a specific job."""
    target_dir = resume_tailorer.tailored_dir / job_id
    pdf_path = target_dir / f"resume_{job_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"No tailored resume found for job ID: {job_id}")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"Resume_{job_id}.pdf"
    )

