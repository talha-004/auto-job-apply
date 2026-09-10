from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.models.job import ApplicationStatus
from app.services.excel_tracker import excel_tracker
from app.services.bot_manager import bot_manager

router = APIRouter()

class ManualReviewResolveRequest(BaseModel):
    job_url: str
    action: str = Field(..., pattern="^(apply_now|mark_applied|dismiss)$")
    notes: Optional[str] = None

@router.get("/list")
async def list_applications(limit: int = 200) -> List[Dict[str, Any]]:
    """Retrieve logged job application records from Excel."""
    return excel_tracker.get_all_records(limit=limit)

@router.get("/manual-review")
async def list_manual_review_queue(limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieve jobs requiring manual attention (unconfirmed submissions, possible duplicates, risk flags)."""
    return excel_tracker.get_manual_review_records(limit=limit)

@router.post("/manual-review/resolve")
async def resolve_manual_review(payload: ManualReviewResolveRequest) -> Dict[str, Any]:
    """Resolve a manual review item with apply_now, mark_applied, or dismiss."""
    if payload.action == "apply_now":
        return await bot_manager.apply_now_manual_job(payload.job_url)
    elif payload.action == "mark_applied":
        success = excel_tracker.update_application_status(
            payload.job_url,
            ApplicationStatus.SUCCESS,
            notes=payload.notes or "Manually marked as applied by user"
        )
        return {"success": success, "message": "Marked job as applied." if success else "Could not find job record."}
    elif payload.action == "dismiss":
        success = excel_tracker.update_application_status(
            payload.job_url,
            ApplicationStatus.SKIPPED,
            notes=payload.notes or "Dismissed from manual review queue by user"
        )
        return {"success": success, "message": "Job dismissed from queue." if success else "Could not find job record."}
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

@router.get("/stats")
async def get_application_stats() -> Dict[str, Any]:
    """Retrieve analytics stats (Total, Success, Failed, Platform breakdowns)."""
    return excel_tracker.get_statistics()

@router.get("/export")
async def export_excel() -> FileResponse:
    """Download the job_applications.xlsx Excel tracking file."""
    file_path = settings.EXCEL_FILE_PATH
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="No application records found yet.")

    return FileResponse(
        path=str(file_path),
        filename="job_applications.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

