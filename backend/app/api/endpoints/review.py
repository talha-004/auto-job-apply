"""
Pre-Submit Review Queue Endpoints.
Allows candidates to inspect pending applications, view answer diffs, and approve or reject them.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from app.services.review_queue import review_queue, ReviewItem
from app.services.policy_engine import policy_engine, AutonomyMode

router = APIRouter()


@router.get("/pending", response_model=List[ReviewItem])
async def get_pending_reviews():
    """Retrieve all applications currently awaiting user approval in the review queue."""
    return review_queue.list_pending()


@router.post("/approve/{review_id}")
async def approve_application(review_id: str):
    """Approve a pending application, allowing submission to proceed."""
    success = review_queue.approve(review_id)
    if not success:
        raise HTTPException(status_code=404, detail="Pending review item not found or already resolved.")
    return {"status": "success", "message": f"Application {review_id} approved for submission."}


@router.post("/reject/{review_id}")
async def reject_application(review_id: str):
    """Reject a pending application, dropping it from the submission pipeline."""
    success = review_queue.reject(review_id)
    if not success:
        raise HTTPException(status_code=404, detail="Pending review item not found or already resolved.")
    return {"status": "success", "message": f"Application {review_id} rejected."}


@router.get("/mode")
async def get_autonomy_mode():
    """Get current autonomy policy mode (assist, supervised, autonomous)."""
    return {"mode": policy_engine.mode.value}


@router.post("/mode/{mode_name}")
async def set_autonomy_mode(mode_name: str):
    """Update current autonomy policy mode."""
    try:
        new_mode = AutonomyMode(mode_name.lower())
        policy_engine.mode = new_mode
        return {"status": "success", "mode": policy_engine.mode.value}
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode. Choose from: {[m.value for m in AutonomyMode]}"
        )
