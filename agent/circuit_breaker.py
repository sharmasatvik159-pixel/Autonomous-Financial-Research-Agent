"""Circuit Breaker Pattern for ARA-1 Tools and External APIs.

Prevents cascading systemic failures by monitoring tool error rates.
Transitions through 3 distinct states:
1. CLOSED: Normal operation. Requests flow freely.
2. OPEN: Tool failure threshold exceeded. Incoming requests fail fast without hitting failing external API.
3. HALF-OPEN: Recovery timeout elapsed. Single trial probe dispatched to test if external service has recovered.
"""

from __future__ import annotations
import logging
import time
from enum import Enum
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger("ARA1.Resilience.CircuitBreaker")

class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreakerOpenException(Exception):
    """Raised when an execution is attempted on a tripped (OPEN) circuit breaker."""
    def __init__(self, tool_name: str, cooldown_remaining: float):
        self.tool_name = tool_name
        self.cooldown_remaining = cooldown_remaining
        super().__init__(
            f"Circuit breaker for '{tool_name}' is OPEN. "
            f"Failing fast to prevent cascading timeout. Retry in {cooldown_remaining:.1f}s."
        )

class CircuitBreaker:
    """Per-tool circuit breaker tracking failure rates, states, and recovery transitions."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 10.0,
        half_open_success_threshold: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.half_open_success_threshold = half_open_success_threshold

        self.state: CircuitState = CircuitState.CLOSED
        self.consecutive_failures: int = 0
        self.consecutive_successes: int = 0
        self.last_failure_time: float = 0.0
        self.total_trips: int = 0

    def can_execute(self) -> bool:
        """Determines if a request is permitted to proceed."""
        now = time.time()

        if self.state == CircuitState.CLOSED:
            return True

        elif self.state == CircuitState.OPEN:
            elapsed = now - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                logger.info(f"Circuit breaker for '{self.name}' transitioning from OPEN to HALF_OPEN (probe enabled).")
                self.state = CircuitState.HALF_OPEN
                self.consecutive_successes = 0
                return True
            return False

        elif self.state == CircuitState.HALF_OPEN:
            return True

        return True

    def record_success(self) -> None:
        """Records a successful tool execution."""
        if self.state == CircuitState.HALF_OPEN:
            self.consecutive_successes += 1
            if self.consecutive_successes >= self.half_open_success_threshold:
                logger.info(f"Probe succeeded. Resetting circuit breaker for '{self.name}' from HALF_OPEN to CLOSED.")
                self.state = CircuitState.CLOSED
                self.consecutive_failures = 0
                self.consecutive_successes = 0
        else:
            self.consecutive_failures = 0

    def record_failure(self, error: Optional[Exception] = None) -> None:
        """Records a failed tool execution and checks trip conditions."""
        self.consecutive_failures += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.CLOSED:
            if self.consecutive_failures >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.total_trips += 1
                logger.warning(
                    f"Failure threshold ({self.failure_threshold}) reached for '{self.name}'. "
                    f"Circuit breaker TRIPPED to OPEN. Cooldown: {self.recovery_timeout}s. Reason: {error}"
                )
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.total_trips += 1
            logger.warning(
                f"Probe execution failed for '{self.name}' in HALF_OPEN state. "
                f"Re-tripping circuit breaker to OPEN for {self.recovery_timeout}s. Error: {error}"
            )

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Executes the callable with circuit protection."""
        if not self.can_execute():
            cooldown = max(0.0, self.recovery_timeout - (time.time() - self.last_failure_time))
            raise CircuitBreakerOpenException(self.name, cooldown)

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(e)
            raise e

    def get_metrics(self) -> Dict[str, Any]:
        """Returns diagnostic metrics for agent trace logging."""
        return {
            "name": self.name,
            "state": self.state.value,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "total_trips": self.total_trips,
            "is_available": self.can_execute(),
        }

class CircuitBreakerRegistry:
    """Manages circuit breakers across all registered tools."""

    def __init__(self, default_failure_threshold: int = 3, default_recovery_timeout: float = 10.0):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self.default_failure_threshold = default_failure_threshold
        self.default_recovery_timeout = default_recovery_timeout

    def get_breaker(self, tool_name: str) -> CircuitBreaker:
        """Retrieves or creates a circuit breaker for a given tool."""
        if tool_name not in self._breakers:
            self._breakers[tool_name] = CircuitBreaker(
                name=tool_name,
                failure_threshold=self.default_failure_threshold,
                recovery_timeout_seconds=self.default_recovery_timeout,
            )
        return self._breakers[tool_name]

    def list_breakers(self) -> Dict[str, CircuitBreaker]:
        """Returns all registered circuit breakers."""
        return dict(self._breakers)

    def is_tool_open(self, tool_name: str) -> bool:
        """Returns True if the circuit breaker for tool_name is currently tripped/OPEN."""
        breaker = self.get_breaker(tool_name)
        return not breaker.can_execute()

    def record_success(self, tool_name: str) -> None:
        self.get_breaker(tool_name).record_success()

    def record_failure(self, tool_name: str, error: Optional[Exception] = None) -> None:
        self.get_breaker(tool_name).record_failure(error)

    def reset_all(self) -> None:
        """Resets all breakers to CLOSED."""
        for b in self._breakers.values():
            b.state = CircuitState.CLOSED
            b.consecutive_failures = 0
            b.consecutive_successes = 0

_GLOBAL_CIRCUIT_REGISTRY: Optional[CircuitBreakerRegistry] = None

def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Singleton provider for global circuit breaker registry."""
    global _GLOBAL_CIRCUIT_REGISTRY
    if _GLOBAL_CIRCUIT_REGISTRY is None:
        _GLOBAL_CIRCUIT_REGISTRY = CircuitBreakerRegistry()
    return _GLOBAL_CIRCUIT_REGISTRY
