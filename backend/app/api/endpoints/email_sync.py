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
