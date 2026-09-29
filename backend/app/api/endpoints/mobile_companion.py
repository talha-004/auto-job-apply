"""
Mobile Companion & Telegram Webhook Gateway Endpoints.
Provides mobile status inspection, webhook update ingestion, and interactive testing.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from app.services.telegram_bot import telegram_companion

router = APIRouter()


class MobileCommandRequest(BaseModel):
    command: str


class SimulateAlertRequest(BaseModel):
    ticket_id: str
    job_title: str
    company: str
    question_text: str
    default_answer: Optional[str] = None


@router.get("/status")
async def get_mobile_companion_status():
    """Returns Telegram companion status and active connection mode."""
    return {
        "is_live": telegram_companion.is_live,
        "mode": "live_telegram" if telegram_companion.is_live else "simulated_loopback",
        "total_dispatched_messages": len(telegram_companion.simulated_dispatches),
        "recent_messages": telegram_companion.simulated_dispatches[-5:]
    }


@router.post("/command")
async def execute_mobile_command(request: MobileCommandRequest):
    """Executes a slash command as if sent from a mobile Telegram client."""
    response_text = await telegram_companion.handle_command(request.command)
    return {"command": request.command, "reply": response_text}


@router.post("/simulate-alert")
async def simulate_mobile_alert(request: SimulateAlertRequest):
    """Simulates an intervention alert pushed to the mobile companion."""
    formatted = telegram_companion.format_intervention_alert(
        ticket_id=request.ticket_id,
        job_title=request.job_title,
        company=request.company,
        question_text=request.question_text,
        default_answer=request.default_answer
    )
    result = await telegram_companion.send_message(
        text=formatted["text"],
        reply_markup=formatted["reply_markup"]
    )
    return {"success": True, "result": result}


@router.post("/telegram/webhook")
async def telegram_webhook_receiver(update: Dict[str, Any] = Body(...)):
    """Receives and processes incoming Telegram Bot webhook updates."""
    # Check for callback query (button press)
    if "callback_query" in update:
        cq = update["callback_query"]
        cb_data = cq.get("data", "")
        sender_id = str(cq.get("from", {}).get("id") or cq.get("message", {}).get("chat", {}).get("id") or "")
        result = await telegram_companion.handle_callback_query(
            cb_data,
            sender_id=sender_id if sender_id else None
        )
        if not result.get("success") and result.get("error") == "Unauthorized chat ID":
            return {"ok": False, "error": "Unauthorized chat ID"}
        return {"ok": True, "type": "callback_query", "action_result": result}

    # Check for direct message (slash command)
    if "message" in update:
        msg = update["message"]
        text = msg.get("text", "")
        sender_id = str(msg.get("chat", {}).get("id") or msg.get("from", {}).get("id") or "")
        reply = await telegram_companion.handle_command(
            text,
            sender_id=sender_id if sender_id else None
        )
        return {"ok": True, "type": "message", "reply": reply}

    return {"ok": True, "ignored": True}
