"""Central Tool Registry for ARA-1 Autonomous Financial Research Agent.

Provides schema registration, OpenAI/Anthropic tool schema generation,
dynamic tool routing, argument validation, fallback execution, and latency tracking.
"""

from __future__ import annotations
import inspect
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable, Type
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("ARA1.ToolRegistry")


class ToolMetadata(BaseModel):
    """Metadata describing a tool and its execution constraints."""
    name: str
    description: str
    category: str = "general"
    rate_limit_rps: float = 10.0
    fallback_tools: List[str] = []
    unlocked: bool = True
    input_schema: Optional[Type[BaseModel]] = None


class ToolResult(BaseModel):
    """Normalized response envelope returned by all tool invocations."""
    tool_name: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    latency_seconds: float = 0.0
    fallback_used: Optional[str] = None
    timestamp: str = ""

    def __init__(self, **data: Any):
        if not data.get("timestamp"):
            data["timestamp"] = datetime.now(timezone.utc).isoformat()
        super().__init__(**data)


class BaseTool:
    """Base class that all financial research tools must implement."""

    def __init__(self, metadata: ToolMetadata):
        self.metadata = metadata

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def description(self) -> str:
        return self.metadata.description

    @property
    def unlocked(self) -> bool:
        return self.metadata.unlocked

    @unlocked.setter
    def unlocked(self, value: bool) -> None:
        self.metadata.unlocked = value

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert tool metadata and Pydantic schema to OpenAI function format."""
        parameters: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}
        if self.metadata.input_schema:
            raw_schema = self.metadata.input_schema.model_json_schema()
            properties = {}
            for prop_name, prop_meta in raw_schema.get("properties", {}).items():
                prop_dict: Dict[str, Any] = {
                    "type": prop_meta.get("type", "string"),
                    "description": prop_meta.get("description", "")
                }
                if "enum" in prop_meta:
                    prop_dict["enum"] = prop_meta["enum"]
                if "default" in prop_meta:
                    prop_dict["default"] = prop_meta["default"]
                properties[prop_name] = prop_dict

            parameters = {
                "type": "object",
                "properties": properties,
                "required": raw_schema.get("required", [])
            }

        return {
            "type": "function",
            "function": {
                "name": self.metadata.name,
                "description": self.metadata.description,
                "parameters": parameters
            }
        }

    def to_anthropic_schema(self) -> Dict[str, Any]:
        """Convert tool metadata and Pydantic schema to Anthropic tool use format."""
        openai_fmt = self.to_openai_schema()
        fn = openai_fmt["function"]
        return {
            "name": fn["name"],
            "description": fn["description"],
            "input_schema": fn["parameters"]
        }

    def validate_args(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate invocation arguments against the tool's input schema."""
        if self.metadata.input_schema:
            try:
                validated = self.metadata.input_schema(**kwargs)
                return validated.model_dump()
            except ValidationError as e:
                raise ValueError(f"Schema validation failed for {self.name}: {e}") from e
        return kwargs

    def run(self, **kwargs: Any) -> Any:
        """Core execution logic to be overridden by concrete tool subclasses."""
        raise NotImplementedError(f"Tool {self.name} has not implemented run()")

    def __call__(self, **kwargs: Any) -> ToolResult:
        """Executes the tool wrapped with validation, timing, and error handling."""
        start_time = time.perf_counter()
        try:
            validated_kwargs = self.validate_args(kwargs)
            result = self.run(**validated_kwargs)
            latency = time.perf_counter() - start_time
            return ToolResult(
                tool_name=self.name,
                success=True,
                data=result,
                latency_seconds=round(latency, 4)
            )
        except Exception as exc:
            latency = time.perf_counter() - start_time
            logger.error(f"Error executing tool {self.name}: {exc}")
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
                latency_seconds=round(latency, 4)
            )


class MockStubTool(BaseTool):
    """Stub tool implementation returning realistic mock responses for testing."""

    def __init__(self, metadata: ToolMetadata, mock_handler: Optional[Callable[..., Any]] = None):
        super().__init__(metadata)
        self.mock_handler = mock_handler

    def run(self, **kwargs: Any) -> Any:
        if self.mock_handler:
            return self.mock_handler(**kwargs)
        return {
            "status": "mock_success",
            "tool": self.name,
            "inputs_received": kwargs,
            "message": f"Simulated output from {self.name}"
        }


class ToolRegistry:
    """Central registry and dispatch engine for agent tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._circuit_breaker_hook: Optional[Callable[[str], bool]] = None

    def register_tool(self, tool: BaseTool) -> None:
        """Register a new tool instance with the registry."""
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool registration: {tool.name}")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} (unlocked={tool.unlocked})")

    def unregister_tool(self, name: str) -> Optional[BaseTool]:
        """Remove a tool from the registry."""
        return self._tools.pop(name, None)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Retrieve a registered tool by its name."""
        return self._tools.get(name)

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def list_tools(self, only_unlocked: bool = True) -> List[str]:
        """List names of registered tools, optionally filtering for unlocked ones."""
        if only_unlocked:
            return [name for name, t in self._tools.items() if t.unlocked]
        return list(self._tools.keys())

    def unlock_tool(self, name: str) -> bool:
        """Dynamically unlock a tool (used for simulation progression unlocks)."""
        tool = self._tools.get(name)
        if tool:
            tool.unlocked = True
            logger.info(f"Dynamically unlocked tool: {name}")
            return True
        return False

    def lock_tool(self, name: str) -> bool:
        """Lock a tool so it is excluded from agent prompts and routing."""
        tool = self._tools.get(name)
        if tool:
            tool.unlocked = False
            return True
        return False

    def get_openai_schemas(self, only_unlocked: bool = True) -> List[Dict[str, Any]]:
        """Export OpenAI function definitions for all registered, unlocked tools."""
        return [
            tool.to_openai_schema()
            for tool in self._tools.values()
            if not only_unlocked or tool.unlocked
        ]

    def get_anthropic_schemas(self, only_unlocked: bool = True) -> List[Dict[str, Any]]:
        """Export Anthropic function/tool definitions for all registered, unlocked tools."""
        return [
            tool.to_anthropic_schema()
            for tool in self._tools.values()
            if not only_unlocked or tool.unlocked
        ]

    def set_circuit_breaker(self, cb_hook: Callable[[str], bool]) -> None:
        """Register a circuit-breaker callback (returns True if circuit is OPEN/tripped)."""
        self._circuit_breaker_hook = cb_hook

    def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        use_fallback: bool = True
    ) -> ToolResult:
        """Route and execute a tool call with circuit breaking and fallback chains."""
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' not found in registry."
            )

        if not tool.unlocked:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' is currently locked. Complete prior milestones to unlock."
            )

        # Check circuit breaker
        if self._circuit_breaker_hook and self._circuit_breaker_hook(tool_name):
            logger.warning(f"Circuit breaker tripped for {tool_name}. Seeking fallback.")
            if use_fallback and tool.metadata.fallback_tools:
                return self._execute_fallback(tool, arguments)
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Circuit breaker OPEN for tool '{tool_name}'. Request halted."
            )

        # Execute primary tool
        result = tool(**arguments)
        if result.success:
            return result

        # Fallback routing on failure (only for runtime/upstream errors, not client schema validation errors)
        is_validation_error = bool(result.error and "validation failed" in result.error.lower())
        if use_fallback and not is_validation_error and tool.metadata.fallback_tools:
            logger.info(f"Tool {tool_name} failed. Attempting fallback chain: {tool.metadata.fallback_tools}")
            return self._execute_fallback(tool, arguments, original_error=result.error)

        return result

    def _execute_fallback(
        self,
        original_tool: BaseTool,
        arguments: Dict[str, Any],
        original_error: Optional[str] = None
    ) -> ToolResult:
        """Traverse the fallback tool chain when a primary tool fails."""
        try:
            from agent.fallback_chains import FallbackChainCoordinator
            coordinator = FallbackChainCoordinator()
        except Exception:
            coordinator = None

        for fallback_name in original_tool.metadata.fallback_tools:
            fallback_tool = self.get_tool(fallback_name)
            if not fallback_tool or not fallback_tool.unlocked:
                continue

            # Check circuit breaker on fallback
            if self._circuit_breaker_hook and self._circuit_breaker_hook(fallback_name):
                continue

            logger.info(f"Invoking fallback tool '{fallback_name}' for '{original_tool.name}'")
            adapted_args = arguments
            if coordinator:
                try:
                    adapted_args = coordinator.adapt_arguments(original_tool.name, fallback_name, arguments)
                except Exception as e:
                    logger.debug(f"Argument adaptation error: {e}")
                    adapted_args = arguments

            fallback_result = fallback_tool(**adapted_args)
            if fallback_result.success:
                fallback_result.fallback_used = fallback_name
                return fallback_result

        return ToolResult(
            tool_name=original_tool.name,
            success=False,
            error=f"Primary tool failed ({original_error}) and all fallbacks exhausted."
        )


def create_default_registry() -> ToolRegistry:
    """Factory creating and populating the default 12-tool registry for ARA-1."""
    from tools.schemas import (
        SecFilingSearchInput,
        WebSearchInput,
        EarningsTranscriptInput,
        FinancialDataApiInput,
        NewsSentimentInput,
        VectorDbSearchInput,
        VectorDbStoreInput,
        CompanyProfileInput,
        PeerComparisonInput,
        CalculationEngineInput,
        FactCheckerInput,
        ReportGeneratorInput,
    )

    from tools.sec_edgar import SecFilingSearchTool
    from tools.financial_api import FinancialDataApiTool
    from tools.web_search import WebSearchTool
    from tools.news_sentiment import NewsSentimentTool
    from tools.memory_tools import VectorDbSearchTool, VectorDbStoreTool
    from tools.earnings import EarningsTranscriptTool
    from tools.company_profile import CompanyProfileTool
    from tools.peer_comparison import PeerComparisonTool
    from tools.calculator import CalculationEngineTool
    from tools.fact_checker import FactCheckerTool
    from tools.report_gen import ReportGeneratorTool

    registry = ToolRegistry()

    # 1. sec_filing_search (Real SEC EDGAR API Integration)
    registry.register_tool(SecFilingSearchTool())

    # 2. web_search (Real Web & Public Search Integration)
    registry.register_tool(WebSearchTool())

    # 3. earnings_transcript (Real Conference Call Q&A Transcript Tool)
    registry.register_tool(EarningsTranscriptTool())

    # 4. financial_data_api (Real yfinance & Market Fundamentals Integration)
    registry.register_tool(FinancialDataApiTool())

    # 5. news_sentiment (Real TextBlob NLP Sentiment Scoring Integration)
    registry.register_tool(NewsSentimentTool())

    # 6. vector_db_search (Real ChromaDB Semantic Search Integration)
    registry.register_tool(VectorDbSearchTool())

    # 7. vector_db_store (Real ChromaDB Document Persistence Integration)
    registry.register_tool(VectorDbStoreTool())

    # 8. company_profile (Real Corporate Entity Profile & Leadership Tool)
    registry.register_tool(CompanyProfileTool())

    # 9. peer_comparison (Real Competitor Multiple Benchmarking & Ranking Tool)
    registry.register_tool(PeerComparisonTool())

    # 10. calculation_engine (Real Deterministic DCF, WACC, CAGR Modeling Tool)
    registry.register_tool(CalculationEngineTool())

    # 11. fact_checker (Real Claim Verification & Contradiction Triangulation Tool)
    registry.register_tool(FactCheckerTool())

    # 12. report_generator (Real Institutional Markdown Synthesis Generator Tool)
    registry.register_tool(ReportGeneratorTool())

    return registry
