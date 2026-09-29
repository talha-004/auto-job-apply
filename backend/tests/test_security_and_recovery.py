import time
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import SecurityManager, security_manager
from app.core.circuit_breaker import CircuitBreakerManager, CircuitState
from app.services.orchestrator import orchestrator
from app.models.job import SearchConfig, DiscoveredJob, JobEvaluationResult, PlatformEnum

client = TestClient(app)


def test_encryption_and_decryption_roundtrip():
    """Verify symmetric encryption and decryption of secrets."""
    secret = "SuperSecretPassword123!@#"
    encrypted = security_manager.encrypt_value(secret)

    assert encrypted != secret
    assert encrypted.startswith("enc:")
    assert security_manager.is_encrypted(encrypted) is True

    decrypted = security_manager.decrypt_value(encrypted)
    assert decrypted == secret


def test_passphrase_derived_key():
    """Verify custom passphrase key derivation via PBKDF2."""
    sec = SecurityManager(custom_key="my-master-passphrase-2026")
    msg = "Confidential API Key: gsk_1234567890abcdef"
    enc = sec.encrypt_value(msg)
    dec = sec.decrypt_value(enc)
    assert dec == msg


def test_decrypt_invalid_or_unencrypted():
    """Verify graceful handling of non-encrypted text and corrupt tokens."""
    plain = "Just a regular non-encrypted string"
    assert security_manager.decrypt_value(plain) == plain

    corrupt = "enc:gAAAAABinvalidTokenString=="
    assert security_manager.decrypt_value(corrupt) == corrupt


def test_dict_encryption_and_decryption():
    """Verify selective encryption of sensitive dictionary keys."""
    creds = {
        "username": "talha_dev",
        "password": "plaintext_password_456",
        "api_key": "sk-123456789012345678901234",
        "other_info": "safe_data"
    }

    enc_creds = security_manager.encrypt_dict(creds)
    assert enc_creds["username"] == "talha_dev"
    assert enc_creds["other_info"] == "safe_data"
    assert enc_creds["password"].startswith("enc:")
    assert enc_creds["api_key"].startswith("enc:")

    dec_creds = security_manager.decrypt_dict(enc_creds)
    assert dec_creds["password"] == "plaintext_password_456"
    assert dec_creds["api_key"] == "sk-123456789012345678901234"


def test_masking_utilities():
    """Verify email, phone, and token masking."""
    masked_email = SecurityManager.mask_email("syedtalha@example.com")
    assert masked_email.endswith("@example.com")
    assert "talha" not in masked_email
    assert masked_email.startswith("s")

    masked_phone = SecurityManager.mask_phone("+919876543210")
    assert masked_phone.startswith("+91")
    assert masked_phone.endswith("210")
    assert "98765" not in masked_phone

    masked_sec = SecurityManager.mask_secret("sk-ant-api03-abcdefghijklmnop", 4, 4)
    assert masked_sec.startswith("sk-a")
    assert masked_sec.endswith("mnop")
    assert "..." in masked_sec


def test_log_sanitization_patterns():
    """Verify text scrubbing of sensitive headers, API keys, URLs, and passwords."""
    raw_log = (
        "Connecting to https://admin:secret123@proxy.com:8080. "
        "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc. "
        "OpenAI key is sk-1234567890abcdef1234567890 and Groq key is gsk_9876543210abcdef1234567890. "
        'Payload: {"password": "SuperSecret", "token": "abcde12345"}'
    )
    cleaned = SecurityManager.sanitize_text(raw_log)

    assert "secret123" not in cleaned
    assert "eyJhbGciOi" not in cleaned
    assert "[REDACTED_OPENAI_KEY]" in cleaned
    assert "[REDACTED_GROQ_KEY]" in cleaned
    assert '"password": "[REDACTED]"' in cleaned
    assert '"token": "[REDACTED]"' in cleaned


def test_circuit_breaker_lifecycle():
    """Verify CLOSED -> OPEN -> HALF_OPEN -> CLOSED state transitions."""
    cb = CircuitBreakerManager()
    service = "test_platform"

    # 1. Initial state is CLOSED
    assert cb.can_execute(service) is True

    # 2. Record 2 failures (threshold is 3)
    cb.record_failure(service, RuntimeError("Fail 1"))
    cb.record_failure(service, RuntimeError("Fail 2"))
    assert cb.can_execute(service) is True

    # 3. Third failure trips circuit to OPEN
    tripped = cb.record_failure(service, RuntimeError("Fail 3"))
    assert tripped is True
    assert cb.can_execute(service) is False

    # 4. Check status report
    status = cb.get_all_status()
    assert service in status
    assert status[service]["state"] == CircuitState.OPEN.value
    assert status[service]["failure_count"] == 3

    # 5. Simulate timeout for HALF_OPEN
    health = cb.get_or_register(service)
    health.recovery_timeout = 0.01  # Set instant recovery for test
    time.sleep(0.02)
    assert cb.can_execute(service) is True
    assert health.state == CircuitState.HALF_OPEN

    # 6. Probe success resets to CLOSED
    cb.record_success(service)
    assert health.state == CircuitState.CLOSED
    assert health.failure_count == 0


def test_circuit_breaker_manual_reset():
    """Verify manual override to reset circuit breaker."""
    cb = CircuitBreakerManager()
    cb.record_failure("naukri", RuntimeError("Captcha"))
    cb.record_failure("naukri", RuntimeError("Captcha"))
    cb.record_failure("naukri", RuntimeError("Captcha"))
    assert cb.can_execute("naukri") is False

    cb.reset("naukri")
    assert cb.can_execute("naukri") is True


def test_orchestrator_crash_checkpoint():
    """Verify atomic saving, loading, and clearing of crash recovery checkpoints."""
    orchestrator.active_run_id = "TEST-RUN-RECOVERY"
    config = SearchConfig(keywords="Python", location="Remote", platforms=[PlatformEnum.LINKEDIN])
    stats = {"applied": 2, "target": 5, "success": 2}

    d_job = DiscoveredJob(
        job_id="test_rec_1",
        title="Software Architect",
        company="TechCorp",
        location="Remote",
        platform="LinkedIn",
        job_url="https://linkedin.com/jobs/view/test-1"
    )
    eval_res = JobEvaluationResult(
        job_id="test_rec_1",
        title="Software Architect",
        company="TechCorp",
        match_score=95,
        priority_score=90,
        is_eligible=True,
        suggested_action="APPLY"
    )

    # 1. Save checkpoint
    orchestrator.save_checkpoint(stats, [(d_job, eval_res)], config)

    # 2. Load checkpoint
    loaded = orchestrator.load_checkpoint()
    assert loaded is not None
    assert loaded["run_id"] == "TEST-RUN-RECOVERY"
    assert loaded["stats"]["applied"] == 2
    assert len(loaded["eligible_jobs"]) == 1
    assert loaded["eligible_jobs"][0]["discovered_job"]["job_id"] == "test_rec_1"

    # 3. Clear checkpoint
    orchestrator.clear_checkpoint()
    assert orchestrator.load_checkpoint() is None


def test_api_security_endpoints():
    """Verify REST endpoints for encryption, decryption, and telemetry."""
    # Status
    status_resp = client.get("/api/security/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["encryption_active"] is True

    # Encrypt
    enc_resp = client.post("/api/security/encrypt", json={"plaintext": "SecretAPIKey"})
    assert enc_resp.status_code == 200
    cipher = enc_resp.json()["ciphertext"]
    assert cipher.startswith("enc:")

    # Decrypt
    dec_resp = client.post("/api/security/decrypt", json={"ciphertext": cipher})
    assert dec_resp.status_code == 200
    assert dec_resp.json()["plaintext"] == "SecretAPIKey"

    # Circuit breakers
    cb_resp = client.get("/api/security/circuit-breakers")
    assert cb_resp.status_code == 200
    assert "circuit_breakers" in cb_resp.json()

    # Reset circuit breaker
    reset_resp = client.post("/api/security/circuit-breakers/linkedin/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["success"] is True
