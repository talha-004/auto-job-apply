from pathlib import Path
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings
from app.services.excel_tracker import excel_tracker

router = APIRouter()

@router.get("/list")
async def list_applications(limit: int = 200) -> List[Dict[str, Any]]:
    """Retrieve logged job application records from Excel."""
    return excel_tracker.get_all_records(limit=limit)

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
