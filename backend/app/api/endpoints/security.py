"""
Security & System Reliability REST API Endpoints.
Provides credential encryption/decryption utilities, circuit breaker telemetry,
and crash recovery checkpoint management.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.security import security_manager
from app.core.circuit_breaker import circuit_breaker
from app.services.orchestrator import orchestrator

router = APIRouter()


class EncryptRequest(BaseModel):
    plaintext: str = Field(..., min_length=1)


class EncryptResponse(BaseModel):
    ciphertext: str
    is_encrypted: bool = True


class DecryptRequest(BaseModel):
    ciphertext: str = Field(..., min_length=1)


class DecryptResponse(BaseModel):
    plaintext: str


@router.get("/status")
async def get_security_status() -> Dict[str, Any]:
    """Retrieve security and hardening telemetry."""
    return {
        "encryption_active": True,
        "log_sanitization_active": True,
        "circuit_breaker_active": True,
        "total_active_breakers": len(circuit_breaker.get_all_status()),
        "has_active_checkpoint": orchestrator.load_checkpoint() is not None
    }


@router.post("/encrypt", response_model=EncryptResponse)
async def encrypt_secret(req: EncryptRequest) -> EncryptResponse:
    """Encrypt a sensitive string using enterprise Fernet symmetric encryption."""
    encrypted = security_manager.encrypt_value(req.plaintext)
    return EncryptResponse(ciphertext=encrypted, is_encrypted=True)


@router.post("/decrypt", response_model=DecryptResponse)
async def decrypt_secret(req: DecryptRequest) -> DecryptResponse:
    """Decrypt a ciphertext token."""
    decrypted = security_manager.decrypt_value(req.ciphertext)
    return DecryptResponse(plaintext=decrypted)


@router.get("/circuit-breakers")
async def get_circuit_breakers() -> Dict[str, Any]:
    """Inspect operational health and trip state of all service circuit breakers."""
    return {
        "circuit_breakers": circuit_breaker.get_all_status()
    }


@router.post("/circuit-breakers/{service}/reset")
async def reset_circuit_breaker(service: str) -> Dict[str, Any]:
    """Manually reset a tripped circuit breaker back to CLOSED state."""
    circuit_breaker.reset(service)
    return {
        "success": True,
        "message": f"Circuit breaker for service '{service}' has been reset to CLOSED."
    }


@router.get("/checkpoint")
async def get_crash_checkpoint() -> Dict[str, Any]:
    """Check for an existing crash recovery checkpoint."""
    checkpoint = orchestrator.load_checkpoint()
    return {
        "has_checkpoint": checkpoint is not None,
        "checkpoint": checkpoint
    }


@router.post("/checkpoint/clear")
async def clear_crash_checkpoint() -> Dict[str, Any]:
    """Discard active crash checkpoint."""
    orchestrator.clear_checkpoint()
    return {
        "success": True,
        "message": "Crash recovery checkpoint cleared."
    }
