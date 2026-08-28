import shutil
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.core.config import settings
from app.core.logger import broadcaster, LogLevel
from app.models.job import ResumeProfile
from app.services.resume_parser import resume_parser_service

router = APIRouter()

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
