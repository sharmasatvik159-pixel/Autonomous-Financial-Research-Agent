"""Agent package for ARA-1 Autonomous Financial Research Agent.

Includes ReAct and Plan-and-Execute reasoning loops, prompt templates,
parsers, error handlers, circuit breakers, and query disambiguation.
"""

from .core import FinancialResearchAgent, AgentExecutionResult
from .llm_client import LLMClient, LLMResponse
from .parser import ReActOutputParser, AgentAction, AgentFinish, PlanOutput
from .logger import AgentLogger, get_agent_logger
from .error_handler import (
    ErrorCategory,
    ErrorSeverity,
    classify_error,
    calculate_backoff_with_jitter,
    retry_with_backoff,
)
from .circuit_breaker import (
    CircuitState,
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitBreakerOpenException,
    get_circuit_breaker_registry,
)
from .fallback_chains import (
    FallbackChainCoordinator,
    FallbackStep,
    FallbackExecutionResult,
    get_fallback_coordinator,
)
from .query_analyzer import (
    QueryScope,
    QueryComplexity,
    AmbiguityLevel,
    EntityLifecycle,
    QueryAnalysisResult,
    QueryAnalyzer,
    get_query_analyzer,
)
from .disambiguation import (
    DisambiguationEngine,
    DisambiguationPlan,
    EdgeCaseGuidance,
    get_disambiguation_engine,
)

__all__ = [
    "FinancialResearchAgent",
    "AgentExecutionResult",
    "LLMClient",
    "LLMResponse",
    "ReActOutputParser",
    "AgentAction",
    "AgentFinish",
    "PlanOutput",
    "AgentLogger",
    "get_agent_logger",
    "ErrorCategory",
    "ErrorSeverity",
    "classify_error",
    "calculate_backoff_with_jitter",
    "retry_with_backoff",
    "CircuitState",
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    "CircuitBreakerOpenException",
    "get_circuit_breaker_registry",
    "FallbackChainCoordinator",
    "FallbackStep",
    "FallbackExecutionResult",
    "get_fallback_coordinator",
    "QueryScope",
    "QueryComplexity",
    "AmbiguityLevel",
    "EntityLifecycle",
    "QueryAnalysisResult",
    "QueryAnalyzer",
    "get_query_analyzer",
    "DisambiguationEngine",
    "DisambiguationPlan",
    "EdgeCaseGuidance",
    "get_disambiguation_engine",
]


