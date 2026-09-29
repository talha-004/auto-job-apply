"""
Circuit Breaker Pattern Implementation for External Platforms and Remote Services.
Protects against cascading failures, IP bans, and rate-limit hammering across
job boards (LinkedIn, Naukri, Indeed) and LLM providers.
"""

import time
from enum import Enum
from typing import Dict, Any, Optional, Callable
from pydantic import BaseModel, Field

from app.core.logger import logger, broadcaster, LogLevel


class CircuitState(str, Enum):
    CLOSED = "CLOSED"       # Normal operation: all traffic allowed
    OPEN = "OPEN"           # Tripped: traffic blocked, fast-fail
    HALF_OPEN = "HALF_OPEN" # Recovery probe: single request allowed to test health


class ServiceHealth(BaseModel):
    service_name: str
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    failure_threshold: int = 3
    recovery_timeout: float = 60.0  # seconds
    last_failure_time: Optional[float] = None
    last_state_change: float = Field(default_factory=time.time)
    last_error: Optional[str] = None


class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""
    def __init__(self, service: str, cooldown_remaining: float):
        self.service = service
        self.cooldown_remaining = round(cooldown_remaining, 1)
        super().__init__(
            f"Circuit breaker for service '{service}' is OPEN. "
            f"Operation halted to prevent ban/overload. Cooldown remaining: {self.cooldown_remaining}s."
        )


class CircuitBreakerManager:
    """Central registry and policy manager for service circuit breakers."""

    def __init__(self):
        self._services: Dict[str, ServiceHealth] = {}

    def get_or_register(
        self,
        service_name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0
    ) -> ServiceHealth:
        """Register or retrieve a service circuit breaker."""
        norm_name = service_name.lower().strip()
        if norm_name not in self._services:
            self._services[norm_name] = ServiceHealth(
                service_name=norm_name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout
            )
        return self._services[norm_name]

    def can_execute(self, service_name: str) -> bool:
        """Determine if a request to the target service is permitted."""
        health = self.get_or_register(service_name)
        now = time.time()

        if health.state == CircuitState.CLOSED:
            return True

        if health.state == CircuitState.OPEN:
            cooldown = now - (health.last_failure_time or health.last_state_change)
            if cooldown >= health.recovery_timeout:
                health.state = CircuitState.HALF_OPEN
                health.last_state_change = now
                logger.info(f"[CircuitBreaker] Service '{service_name}' transitioned from OPEN to HALF_OPEN (probing).")
                return True
            return False

        if health.state == CircuitState.HALF_OPEN:
            # Allow trial probe
            return True

        return False

    def record_success(self, service_name: str):
        """Record successful execution; reset failure counter and close circuit."""
        health = self.get_or_register(service_name)
        if health.state != CircuitState.CLOSED:
            logger.info(f"[CircuitBreaker] Service '{service_name}' recovered! Transitioning to CLOSED.")
        health.state = CircuitState.CLOSED
        health.failure_count = 0
        health.last_error = None
        health.last_state_change = time.time()

    def record_failure(self, service_name: str, error: Optional[Exception] = None) -> bool:
        """
        Record failed execution. Returns True if the circuit tripped to OPEN.
        """
        health = self.get_or_register(service_name)
        health.failure_count += 1
        now = time.time()
        health.last_failure_time = now
        health.last_error = str(error) if error else "Unknown error"

        if health.failure_count >= health.failure_threshold and health.state != CircuitState.OPEN:
            health.state = CircuitState.OPEN
            health.last_state_change = now
            logger.warning(
                f"[CircuitBreaker] Service '{service_name}' TRIPPED to OPEN after {health.failure_count} consecutive failures! "
                f"Cooldown period: {health.recovery_timeout}s."
            )
            return True

        return False

    def reset(self, service_name: str):
        """Manually reset a circuit breaker to CLOSED state."""
        health = self.get_or_register(service_name)
        health.state = CircuitState.CLOSED
        health.failure_count = 0
        health.last_error = None
        health.last_state_change = time.time()
        logger.info(f"[CircuitBreaker] Service '{service_name}' manually reset to CLOSED.")

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Return status dictionary of all registered circuit breakers."""
        now = time.time()
        result = {}
        for name, h in self._services.items():
            cooldown_left = 0.0
            if h.state == CircuitState.OPEN:
                elapsed = now - (h.last_failure_time or h.last_state_change)
                cooldown_left = max(0.0, h.recovery_timeout - elapsed)

            result[name] = {
                "service": name,
                "state": h.state.value,
                "failure_count": h.failure_count,
                "failure_threshold": h.failure_threshold,
                "recovery_timeout": h.recovery_timeout,
                "cooldown_remaining_sec": round(cooldown_left, 1),
                "last_error": h.last_error
            }
        return result


circuit_breaker = CircuitBreakerManager()
