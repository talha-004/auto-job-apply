"""
AI Mock Interview Coach Endpoints.
Provides interview preparation package generation and practice answer evaluation.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

from app.services.interview_coach import (
    interview_coach_service,
    InterviewPrepPackage,
    PracticeFeedback
)

router = APIRouter()


class GeneratePrepRequest(BaseModel):
    job_id: str
    job_title: str
    company: str
    job_description: Optional[str] = ""


class PracticeAnswerRequest(BaseModel):
    question: str
    user_answer: str
    expected_concepts: Optional[List[str]] = None


@router.post("/generate", response_model=InterviewPrepPackage)
async def generate_interview_prep(request: GeneratePrepRequest):
    """Generates or retrieves role & company tailored interview prep."""
    pkg = await interview_coach_service.generate_prep_package(
        job_id=request.job_id,
        job_title=request.job_title,
        company=request.company,
        job_description=request.job_description or ""
    )
    return pkg


@router.get("/prep/{job_id}", response_model=InterviewPrepPackage)
async def get_prep_by_job_id(job_id: str, job_title: str = "Software Engineer", company: str = "Target Company"):
    """Fetches prep package for a given application ID."""
    pkg = await interview_coach_service.generate_prep_package(
        job_id=job_id,
        job_title=job_title,
        company=company
    )
    return pkg


@router.post("/practice/evaluate", response_model=PracticeFeedback)
async def evaluate_practice_answer(request: PracticeAnswerRequest):
    """Scores a candidate's answer and returns actionable feedback."""
    feedback = await interview_coach_service.evaluate_practice_response(
        question=request.question,
        user_answer=request.user_answer,
        expected_concepts=request.expected_concepts
    )
    return feedback
