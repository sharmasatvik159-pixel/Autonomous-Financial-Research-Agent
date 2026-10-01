"""Day 9 Resilience, Error Handling, Fallback Chains & Circuit Breaker Test Suite.

Tests agent error recovery systems under agent/:
- agent/error_handler.py: Exponential backoff with jitter and error categorization
- agent/circuit_breaker.py: Circuit breaker state machine (CLOSED -> OPEN -> HALF-OPEN -> CLOSED)
- agent/fallback_chains.py: Multi-stage fallback routing, schema argument adaptation, and graceful degradation
"""

import pytest
import time
from agent.error_handler import (
    ErrorCategory,
    ErrorSeverity,
    classify_error,
    calculate_backoff_with_jitter,
    retry_with_backoff,
)
from agent.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenException,
    CircuitBreakerRegistry,
)
from agent.fallback_chains import (
    FallbackChainCoordinator,
    FallbackExecutionResult,
)

def test_error_classification():
    """Verify exceptions are properly classified into transient vs fatal categories."""
    cat1, sev1 = classify_error(Exception("429 Too Many Requests: Rate limit exceeded"))
    assert cat1 == ErrorCategory.RATE_LIMIT
    assert sev1 == ErrorSeverity.TRANSIENT

    cat2, sev2 = classify_error(TimeoutError("Connection timed out after 30s"))
    assert cat2 == ErrorCategory.TIMEOUT
    assert sev2 == ErrorSeverity.TRANSIENT

    cat3, sev3 = classify_error(Exception("500 Internal Server Error: Gateway timeout 504"))
    assert cat3 == ErrorCategory.SERVER_5XX
    assert sev3 == ErrorSeverity.TRANSIENT

    cat4, sev4 = classify_error(Exception("Schema validation error: field missing"))
    assert cat4 == ErrorCategory.SCHEMA_ERROR
    assert sev4 == ErrorSeverity.DEGRADED

def test_exponential_backoff_jitter():
    """Verify exponential backoff calculation increases and applies bounded jitter."""
    delays = [calculate_backoff_with_jitter(attempt=i, base_delay=0.1, max_delay=5.0) for i in range(1, 5)]
    assert len(delays) == 4
    for d in delays:
        assert d >= 0.05
    assert delays[-1] > delays[0]

def test_retry_with_backoff_transient_recovery():
    """Verify retry decorator retries on transient errors and succeeds when service recovers."""
    attempts = 0

    @retry_with_backoff(max_retries=3, base_delay=0.01, max_delay=0.05)
    def flaky_service():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise Exception("503 Service Unavailable: Simulated transient outage")
        return "SUCCESS_DATA"

    result = flaky_service()
    assert result == "SUCCESS_DATA"
    assert attempts == 3

def test_circuit_breaker_tripping_and_recovery():
    """Verify circuit breaker transitions: CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
    cb = CircuitBreaker(
        name="test_tool",
        failure_threshold=2,
        recovery_timeout_seconds=0.2,
        half_open_success_threshold=1,
    )
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True

    cb.record_failure(Exception("500 Server Error"))
    assert cb.state == CircuitState.CLOSED
    assert cb.consecutive_failures == 1

    cb.record_failure(Exception("500 Server Error"))
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False
    assert cb.total_trips == 1

    with pytest.raises(CircuitBreakerOpenException):
        cb.execute(lambda: "should_not_run")

    time.sleep(0.25)
    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.consecutive_failures == 0

def test_fallback_chain_primary_failure_recovery():
    """Verify primary tool failure automatically routes to secondary fallback tool."""
    coordinator = FallbackChainCoordinator(
        custom_chains={"primary_api": ["secondary_api", "tertiary_api"]}
    )

    def mock_executor(tool_name: str, args: dict):
        if tool_name == "primary_api":
            raise Exception("500 Server Error on primary")
        elif tool_name == "secondary_api":
            return {"status": "ok", "source": "secondary_api", "data": "recovered_financial_data"}
        return None

    res = coordinator.execute_with_fallback(
        primary_tool="primary_api",
        original_args={"ticker": "JPM", "statement_type": "income_statement"},
        tool_executor=mock_executor,
    )

    assert res.success is True
    assert res.fallback_occurred is True
    assert res.executed_tool == "secondary_api"
    assert res.data["data"] == "recovered_financial_data"
    assert len(res.hops_taken) == 2
    assert res.hops_taken[0].status == "FAILED"
    assert res.hops_taken[1].status == "SUCCESS"

def test_fallback_chain_graceful_degradation():
    """Verify graceful degradation when every tool in the fallback chain fails."""
    coordinator = FallbackChainCoordinator(
        custom_chains={"flaky_primary": ["flaky_backup"]}
    )

    def failing_executor(tool_name: str, args: dict):
        raise TimeoutError(f"Connection timeout on {tool_name}")

    res = coordinator.execute_with_fallback(
        primary_tool="flaky_primary",
        original_args={"ticker": "SVB"},
        tool_executor=failing_executor,
    )

    assert res.success is False
    assert res.is_degraded is True
    assert res.executed_tool == "graceful_degradation"
    assert "temporarily unavailable" in res.degraded_summary
    alert_md = coordinator.render_degradation_alert_markdown()
    assert "Data Availability & Graceful Degradation Notice" in alert_md
    assert "flaky_primary" in alert_md

def test_fallback_argument_adaptation():
    """Verify automatic adaptation of query arguments between different tool schemas."""
    coordinator = FallbackChainCoordinator()

    orig = {"ticker": "BAC", "statement_type": "income_statement", "period": "annual"}
    adapted = coordinator.adapt_arguments("financial_data_api", "sec_filing_search", orig)
    assert adapted["ticker"] == "BAC"
    assert adapted["filing_type"] == "10-K"

    orig_peer = {"ticker": "WFC", "num_peers": 4}
    adapted_peer = coordinator.adapt_arguments("peer_comparison", "company_profile", orig_peer)
    assert adapted_peer == {"ticker": "WFC"}
