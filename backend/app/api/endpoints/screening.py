from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.services.screening_service import (
    screening_service,
    ScreeningQuestionRequest,
    ScreeningQuestionAnswer
)
from app.core.llm import llm_client

router = APIRouter()


class ScreeningBatchRequest(BaseModel):
    questions: List[ScreeningQuestionRequest]
    job_context: Optional[Dict[str, Any]] = None


@router.post("/answer", response_model=ScreeningQuestionAnswer)
async def answer_screening_question(request: ScreeningQuestionRequest):
    """
    Answer an individual screening question using candidate's QA Vault and LLM reasoning.
    Categorizes answer into EXACT_VAULT, DERIVED, or UNKNOWN (requiring human intervention).
    """
    try:
        result = await screening_service.answer_question(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process screening question: {str(e)}")


@router.post("/batch", response_model=List[ScreeningQuestionAnswer])
async def answer_screening_questions_batch(batch_request: ScreeningBatchRequest):
    """
    Answer a batch of screening questions for a job application form.
    """
    try:
        results = await screening_service.answer_batch(
            requests=batch_request.questions,
            job_context=batch_request.job_context
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process screening batch: {str(e)}")


@router.get("/providers")
async def get_llm_providers_status():
    """
    Check availability and operational status of all configured LLM providers (Ollama, Gemini, DeepSeek, Groq).
    """
    return await llm_client.check_health()
