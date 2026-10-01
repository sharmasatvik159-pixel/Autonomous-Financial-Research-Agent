"""LLM Client Wrapper for ARA-1 with Tenacity Retry Logic and Token Tracking.

Wraps LangChain ChatOpenAI models (and mock fallbacks for offline testing)
with exponential backoff retries, precise token counting, latency benchmarking,
and cost accounting.
"""

from __future__ import annotations
import os
import time
import logging
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field

from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    AIMessage,
)
from langchain_core.outputs import ChatGeneration, LLMResult

from config.settings import get_settings
from agent.logger import get_agent_logger

logger = logging.getLogger("ARA1.LLMClient")

# Token pricing approximations per 1M tokens (USD)
MODEL_PRICING = {
    "gpt-4o": {"input": 5.00, "output": 15.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "text-embedding-3-small": {"input": 0.02, "output": 0.00},
    "text-embedding-3-large": {"input": 0.13, "output": 0.00},
}


class TokenUsageRecord(BaseModel):
    """Cumulative token tracking record."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_calls: int = 0
    total_latency_seconds: float = 0.0
    estimated_cost_usd: float = 0.0

    def add(
        self,
        prompt: int,
        completion: int,
        latency: float,
        model_name: str
    ) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += (prompt + completion)
        self.total_calls += 1
        self.total_latency_seconds += latency

        pricing = MODEL_PRICING.get(model_name, {"input": 2.0, "output": 6.0})
        call_cost = (prompt * pricing["input"] / 1_000_000.0) + (completion * pricing["output"] / 1_000_000.0)
        self.estimated_cost_usd += call_cost


class LLMResponse(BaseModel):
    """Normalized response structure from LLM call."""
    content: str
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_seconds: float = 0.0
    cost_usd: float = 0.0
    model: str = ""


class MockChatModel:
    """Offline mock model providing deterministic responses for unit testing."""

    def __init__(self, model_name: str = "mock-gpt-4o"):
        self.model_name = model_name

    def invoke(
        self,
        messages: List[BaseMessage],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AIMessage:
        time.sleep(0.02)  # Simulate small network latency
        last_msg = messages[-1].content if messages else ""
        content = (
            f"MOCK_ANALYSIS: Processed query successfully. "
            f"Observations synthesized for financial query: '{last_msg[:60]}'."
        )
        return AIMessage(
            content=content,
            response_metadata={"token_usage": {"prompt_tokens": 85, "completion_tokens": 42}}
        )


class LLMClient:
    """Resilient LLM client for ARA-1 with Tenacity retries and token metrics."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        force_mock: bool = False,
    ):
        self.settings = get_settings()
        self.model_name = model_name or self.settings.DEFAULT_LLM_MODEL
        self.temperature = temperature if temperature is not None else self.settings.TEMPERATURE
        self.max_tokens = max_tokens or self.settings.MAX_TOKENS
        self.usage = TokenUsageRecord()
        self.agent_logger = get_agent_logger()

        # Decide whether to use real ChatOpenAI or MockChatModel
        self.is_mock = force_mock or self.settings.MOCK_MODE or not self.settings.is_openai_configured()

        if self.is_mock:
            logger.info(f"LLMClient running in MOCK mode (model: {self.model_name})")
            self._chat_model = MockChatModel(model_name=self.model_name)
        else:
            from langchain_openai import ChatOpenAI
            logger.info(f"LLMClient initialized with ChatOpenAI (model: {self.model_name})")
            self._chat_model = ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=self.settings.OPENAI_API_KEY,
                max_retries=1,  # Tenacity handles retries explicitly
            )

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError, Exception)),
        wait=wait_random_exponential(min=1, max=10),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _execute_with_retry(
        self,
        messages: List[BaseMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        """Invokes model under tenacity retry guard."""
        if hasattr(self._chat_model, "bind_tools") and tools:
            # Bind tools if supported
            bound_model = self._chat_model.bind_tools(tools)
            return bound_model.invoke(messages)
        return self._chat_model.invoke(messages)

    def invoke(
        self,
        prompt_or_messages: Union[str, List[BaseMessage]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Synchronously invokes the LLM, tracking tokens, cost, and latency."""
        start_time = time.perf_counter()

        if isinstance(prompt_or_messages, str):
            messages = [HumanMessage(content=prompt_or_messages)]
        else:
            messages = prompt_or_messages

        try:
            ai_msg = self._execute_with_retry(messages, tools=tools)
            latency = time.perf_counter() - start_time

            # Extract token metadata
            meta = getattr(ai_msg, "response_metadata", {}) or {}
            usage_dict = meta.get("token_usage", {}) or meta.get("usage", {})
            prompt_tokens = usage_dict.get("prompt_tokens", len(str(messages)) // 4)
            completion_tokens = usage_dict.get("completion_tokens", len(ai_msg.content) // 4)

            # Extract tool calls if present
            tool_calls = []
            if hasattr(ai_msg, "tool_calls") and ai_msg.tool_calls:
                for tc in ai_msg.tool_calls:
                    tool_calls.append({
                        "name": tc.get("name"),
                        "args": tc.get("args", {}),
                        "id": tc.get("id"),
                    })

            # Record usage
            self.usage.add(prompt_tokens, completion_tokens, latency, self.model_name)

            pricing = MODEL_PRICING.get(self.model_name, {"input": 0.15, "output": 0.60})
            cost = (prompt_tokens * pricing["input"] + completion_tokens * pricing["output"]) / 1_000_000.0

            # Log to agent logger
            self.agent_logger.log_llm_call(
                model=self.model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_seconds=round(latency, 3),
                estimated_cost_usd=cost,
            )

            return LLMResponse(
                content=ai_msg.content if isinstance(ai_msg.content, str) else str(ai_msg.content),
                tool_calls=tool_calls,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                latency_seconds=round(latency, 4),
                cost_usd=round(cost, 6),
                model=self.model_name,
            )

        except Exception as exc:
            latency = time.perf_counter() - start_time
            self.agent_logger.log_error("LLMClient", f"Invocation failed on {self.model_name}: {exc}", exc)
            raise

    def get_usage_summary(self) -> Dict[str, Any]:
        """Returns cumulative token and financial metrics."""
        return {
            "model_name": self.model_name,
            "prompt_tokens": self.usage.prompt_tokens,
            "completion_tokens": self.usage.completion_tokens,
            "total_tokens": self.usage.total_tokens,
            "total_calls": self.usage.total_calls,
            "total_latency_seconds": round(self.usage.total_latency_seconds, 3),
            "estimated_cost_usd": round(self.usage.estimated_cost_usd, 5),
            "is_mock": self.is_mock,
        }

    def reset_usage(self) -> None:
        """Resets the usage tracker."""
        self.usage = TokenUsageRecord()
