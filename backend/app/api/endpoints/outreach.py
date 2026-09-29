from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.job import (
    RecruiterContact,
    OutreachMessage,
    OutreachChannel,
    OutreachStatus
)
from app.services.contact_extractor import contact_extractor_service
from app.services.email_outreach_service import email_outreach_service

router = APIRouter()


class ContactExtractionRequest(BaseModel):
    jd_text: str
    recruiter_text: Optional[str] = None
    company: Optional[str] = None


class DraftOutreachRequest(BaseModel):
    job_id: str
    job_title: str
    company: str
    recipient: RecruiterContact
    channel: OutreachChannel = OutreachChannel.EMAIL
    attachment_path: Optional[str] = None


class SendOutreachRequest(BaseModel):
    outreach_id: str
    force_send: bool = False


@router.post("/extract-contacts", response_model=List[RecruiterContact])
async def extract_contacts(request: ContactExtractionRequest):
    """
    Extract recruiter emails, phone numbers, names, and WhatsApp details from job text.
    """
    try:
        contacts = contact_extractor_service.extract_contacts(
            jd_text=request.jd_text,
            recruiter_text=request.recruiter_text,
            company=request.company
        )
        return contacts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract contacts: {str(e)}")


@router.post("/draft", response_model=OutreachMessage)
async def draft_outreach_message(request: DraftOutreachRequest):
    """
    Generate a personalized cold outreach email or WhatsApp message tailored to the role.
    """
    try:
        msg = await email_outreach_service.draft_outreach(
            job_id=request.job_id,
            job_title=request.job_title,
            company=request.company,
            recipient=request.recipient,
            channel=request.channel,
            attachment_path=request.attachment_path
        )
        return msg
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to draft outreach: {str(e)}")


@router.get("/messages", response_model=List[OutreachMessage])
async def list_outreach_messages(
    status: Optional[OutreachStatus] = None,
    limit: int = Query(default=50, ge=1, le=200)
):
    """
    List all drafted, ready, and sent outreach communications.
    """
    return email_outreach_service.list_outreach_messages(status=status, limit=limit)


@router.get("/messages/{outreach_id}", response_model=OutreachMessage)
async def get_outreach_message(outreach_id: str):
    """
    Retrieve specific outreach message details by ID.
    """
    msg = email_outreach_service.get_outreach(outreach_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Outreach message not found.")
    return msg


@router.post("/send", response_model=OutreachMessage)
async def send_outreach_email(request: SendOutreachRequest):
    """
    Send an approved outreach email via SMTP with resume attachment.
    Requires force_send=True to confirm user approval if safety guard is active.
    """
    try:
        sent_msg = email_outreach_service.send_email(
            outreach_id=request.outreach_id,
            force_send=request.force_send
        )
        return sent_msg
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


@router.get("/whatsapp-url")
async def get_whatsapp_url(phone: str, message: str):
    """
    Generate a WhatsApp click-to-chat URL with pre-filled message.
    """
    url = email_outreach_service.generate_whatsapp_url(phone=phone, message=message)
    return {"whatsapp_url": url}


@router.post("/decline/{outreach_id}")
async def decline_outreach_message(outreach_id: str):
    """
    Decline/dismiss a drafted recruiter outreach message.
    """
    msg = email_outreach_service.get_outreach(outreach_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Outreach message not found.")
    msg.status = OutreachStatus.DECLINED
    email_outreach_service._save_outreach(msg)
    return {"success": True, "message": "Outreach message declined."}

