"""Unit tests for LLMClient and token tracking."""

import pytest
from agent.llm_client import LLMClient
from agent.logger import get_agent_logger

def test_llm_client_mock_invocation():
    """Verify LLM client produces structured responses in mock mode."""
    client = LLMClient(force_mock=True)
    res = client.invoke("Analyze Apple's gross margin performance")

    assert res.content is not None
    assert "MOCK_ANALYSIS" in res.content
    assert res.prompt_tokens > 0
    assert res.completion_tokens > 0
    assert res.total_tokens == res.prompt_tokens + res.completion_tokens
    assert res.latency_seconds >= 0.0

def test_llm_client_usage_accumulation():
    """Verify cumulative token and cost tracking across multiple invocations."""
    client = LLMClient(force_mock=True)
    client.reset_usage()

    res1 = client.invoke("Query 1: Tesla deliveries")
    res2 = client.invoke("Query 2: Amazon AWS margins")

    summary = client.get_usage_summary()
    assert summary["total_calls"] == 2
    assert summary["total_tokens"] == res1.total_tokens + res2.total_tokens
    assert summary["estimated_cost_usd"] > 0.0

def test_agent_logger_trace_recording():
    """Verify logger records thought, action, observation, and LLM calls."""
    logger = get_agent_logger("test-trace-session")
    logger.reset_trace("test-trace-session")

    logger.log_thought(1, "Formulating plan for Palantir", "Palantir Research")
    logger.log_action(1, "sec_filing_search", {"ticker": "PLTR", "filing_type": "10-K"})
    logger.log_observation(1, "sec_filing_search", "10-K filing retrieved", 0.25, success=True)

    trace = logger.get_active_trace()
    assert len(trace) == 3
    assert trace[0]["event_type"] == "thought"
    assert trace[1]["event_type"] == "action"
    assert trace[2]["event_type"] == "observation"
