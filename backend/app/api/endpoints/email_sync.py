"""
Inbound Email Sync & Recruiter Communication Endpoints.
Provides endpoints for manual/scheduled mailbox polling, simulated email ingestion,
and inspection of auto-classified recruiter responses.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from app.services.email_sync import email_sync_service, ClassifiedEmailRecord

router = APIRouter()


class SimulateEmailPayload(BaseModel):
    sender: str
    subject: str
    body: str


class EmailSyncConfigPayload(BaseModel):
    host: str
    port: int = 993
    user: str
    password: str
    use_ssl: bool = True


@router.post("/sync", response_model=List[ClassifiedEmailRecord])
async def trigger_email_sync(max_emails: int = 15):
    """Triggers an IMAP mailbox synchronization or returns processed records."""
    records = await email_sync_service.sync_mailbox(max_emails=max_emails)
    return records


@router.get("/classified", response_model=List[ClassifiedEmailRecord])
async def get_classified_emails(limit: int = 25):
    """Lists history of classified recruiter messages and status updates."""
    return email_sync_service.history[-limit:]


@router.post("/simulate", response_model=ClassifiedEmailRecord)
async def simulate_inbound_email(payload: SimulateEmailPayload):
    """
    Ingests and processes a simulated recruiter email.
    Useful for testing automatic status transition to INTERVIEW_SCHEDULED or REJECTED.
    """
    record = await email_sync_service.ingest_and_process_email(
        sender=payload.sender,
        subject=payload.subject,
        body=payload.body
    )
    return record


class EditRSVPDraftPayload(BaseModel):
    body: str
    subject: Optional[str] = None


@router.get("/rsvp-drafts")
async def list_rsvp_drafts(status: Optional[str] = None):
    """Lists generated recruiter RSVP response drafts."""
    from app.services.email_auto_responder import email_auto_responder
    return email_auto_responder.list_drafts(status=status)


@router.get("/rsvp-drafts/{draft_id}")
async def get_rsvp_draft(draft_id: str):
    """Retrieves a single recruiter RSVP reply draft."""
    from app.services.email_auto_responder import email_auto_responder
    draft = email_auto_responder.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="RSVP draft not found.")
    return draft


@router.post("/rsvp-drafts/{draft_id}/send")
async def send_rsvp_draft(draft_id: str):
    """Approves and dispatches the drafted recruiter RSVP."""
    from app.services.email_auto_responder import email_auto_responder
    res = email_auto_responder.send_rsvp(draft_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Failed to send RSVP draft."))
    return res


@router.post("/rsvp-drafts/{draft_id}/edit")
async def edit_rsvp_draft(draft_id: str, payload: EditRSVPDraftPayload):
    """Edits the subject or body of a pending RSVP draft."""
    from app.services.email_auto_responder import email_auto_responder
    draft = email_auto_responder.edit_draft(draft_id, new_body=payload.body, new_subject=payload.subject)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found or not in editable state.")
    return draft


@router.post("/rsvp-drafts/{draft_id}/dismiss")
async def dismiss_rsvp_draft(draft_id: str):
    """Dismisses an unneeded RSVP draft."""
    from app.services.email_auto_responder import email_auto_responder
    success = email_auto_responder.dismiss_draft(draft_id)
    if not success:
        raise HTTPException(status_code=404, detail="Draft not found or cannot be dismissed.")
    return {"success": True, "draft_id": draft_id, "status": "DISMISSED"}

