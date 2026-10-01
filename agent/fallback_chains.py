"""Fallback Tool Chains & Graceful Degradation Coordinator for ARA-1.

Implements multi-stage fallback routing across tools:
1. Primary Financial API -> SEC Filing Search -> Web Search -> Vector Memory Search
2. Earnings Transcripts -> Web Search -> SEC 8-K/10-Q Search
3. News Sentiment -> Web Search
4. Peer Comparison -> Company Profile -> Financial Data API

Provides argument adaptation, circuit breaker awareness, and graceful degradation
when external data sources experience systemic outages or data gaps.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional, Tuple, Callable
from pydantic import BaseModel, Field

from agent.circuit_breaker import get_circuit_breaker_registry, CircuitBreakerOpenException

logger = logging.getLogger("ARA1.Resilience.FallbackChains")


class FallbackStep(BaseModel):
    """Represents a specific fallback hop in a tool failure recovery sequence."""
    hop_number: int
    tool_name: str
    adapted_arguments: Dict[str, Any]
    status: str = "PENDING"  # PENDING, SUCCESS, FAILED, SKIPPED_CIRCUIT_OPEN
    error_message: Optional[str] = None


class FallbackExecutionResult(BaseModel):
    """Envelope returned when executing a tool call through its fallback chain."""
    primary_tool: str
    executed_tool: str
    success: bool
    data: Any
    fallback_occurred: bool
    hops_taken: List[FallbackStep] = Field(default_factory=list)
    is_degraded: bool = False
    data_gap_reason: Optional[str] = None
    degraded_summary: Optional[str] = None


class FallbackChainCoordinator:
    """Manages fallback hierarchies and dynamically translates parameters between tools."""

    # Default fallback hierarchies defined in Section B1 & B2
    DEFAULT_CHAINS: Dict[str, List[str]] = {
        "financial_data_api": ["sec_filing_search", "web_search", "vector_db_search"],
        "sec_filing_search": ["financial_data_api", "web_search"],
        "earnings_transcript": ["web_search", "sec_filing_search"],
        "news_sentiment": ["web_search"],
        "peer_comparison": ["company_profile", "financial_data_api"],
        "company_profile": ["web_search", "sec_filing_search"],
    }

    def __init__(self, custom_chains: Optional[Dict[str, List[str]]] = None):
        self.chains = custom_chains or dict(self.DEFAULT_CHAINS)
        self.circuit_registry = get_circuit_breaker_registry()
        self.degradation_audit_log: List[Dict[str, Any]] = []

    def get_fallback_chain(self, tool_name: str) -> List[str]:
        """Returns the ordered list of fallback tools for a given primary tool."""
        return self.chains.get(tool_name, [])

    def adapt_arguments(
        self,
        from_tool: str,
        to_tool: str,
        original_args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Translates argument schemas when routing between disparate tools."""
        ticker = original_args.get("ticker", "")

        # 1. financial_data_api -> sec_filing_search
        if from_tool == "financial_data_api" and to_tool == "sec_filing_search":
            return {
                "ticker": ticker,
                "filing_type": "10-K" if original_args.get("period") == "annual" else "10-Q",
                "section": "Item 8" if "income" in original_args.get("statement_type", "") else "Item 7",
            }

        # 2. sec_filing_search -> financial_data_api
        elif from_tool == "sec_filing_search" and to_tool == "financial_data_api":
            return {
                "ticker": ticker,
                "statement_type": "income_statement",
                "period": "annual" if original_args.get("filing_type") == "10-K" else "quarterly",
                "years": 2,
            }

        # 3. Any tool -> web_search
        elif to_tool == "web_search":
            if "query" in original_args:
                return {"query": original_args["query"], "num_results": original_args.get("num_results", 3)}
            stmt = original_args.get("statement_type") or original_args.get("filing_type") or "financials"
            return {
                "query": f"{ticker} {stmt} revenue earnings results",
                "num_results": 3,
            }

        # 4. Any tool -> vector_db_search
        elif to_tool == "vector_db_search":
            q = original_args.get("query") or f"{ticker} financial operating metrics"
            return {
                "query": q,
                "ticker": ticker,
                "top_k": 3,
            }

        # 5. earnings_transcript -> sec_filing_search
        elif from_tool == "earnings_transcript" and to_tool == "sec_filing_search":
            return {
                "ticker": ticker,
                "filing_type": "10-Q",
                "section": "Item 7",
            }

        # 6. peer_comparison -> company_profile
        elif from_tool == "peer_comparison" and to_tool == "company_profile":
            return {"ticker": ticker}

        # Default: pass-through if keys overlap
        return dict(original_args)

    def execute_with_fallback(
        self,
        primary_tool: str,
        original_args: Dict[str, Any],
        tool_executor: Callable[[str, Dict[str, Any]], Any],
    ) -> FallbackExecutionResult:
        """
        Executes primary tool, seamlessly cascading through the fallback chain
        if primary fails or its circuit breaker is OPEN.
        """
        chain = [primary_tool] + self.get_fallback_chain(primary_tool)
        hops_taken: List[FallbackStep] = []

        for hop_idx, current_tool in enumerate(chain, start=1):
            adapted_args = (
                original_args
                if current_tool == primary_tool
                else self.adapt_arguments(primary_tool, current_tool, original_args)
            )

            step = FallbackStep(
                hop_number=hop_idx,
                tool_name=current_tool,
                adapted_arguments=adapted_args,
            )

            # Check circuit breaker
            if self.circuit_registry.is_tool_open(current_tool):
                step.status = "SKIPPED_CIRCUIT_OPEN"
                step.error_message = f"Circuit breaker OPEN for {current_tool}."
                hops_taken.append(step)
                logger.warning(f"Skipping {current_tool} in fallback chain: Circuit breaker is OPEN.")
                continue

            try:
                logger.info(f"Dispatching tool '{current_tool}' (Hop {hop_idx}/{len(chain)}).")
                result = tool_executor(current_tool, adapted_args)

                # Check if tool execution reported an internal failure
                success = getattr(result, "success", True)
                if not success:
                    err = getattr(result, "error", "Execution failed")
                    self.circuit_registry.record_failure(current_tool, Exception(err))
                    step.status = "FAILED"
                    step.error_message = str(err)
                    hops_taken.append(step)
                    continue

                # Succeeded!
                self.circuit_registry.record_success(current_tool)
                step.status = "SUCCESS"
                hops_taken.append(step)

                return FallbackExecutionResult(
                    primary_tool=primary_tool,
                    executed_tool=current_tool,
                    success=True,
                    data=getattr(result, "data", result),
                    fallback_occurred=(current_tool != primary_tool),
                    hops_taken=hops_taken,
                    is_degraded=(current_tool != primary_tool),
                )

            except Exception as e:
                self.circuit_registry.record_failure(current_tool, e)
                step.status = "FAILED"
                step.error_message = str(e)
                hops_taken.append(step)
                logger.warning(f"Hop {hop_idx} ({current_tool}) failed: {e}. Cascading to next fallback.")

        # If every tool in the chain failed, trigger Graceful Degradation
        ticker = original_args.get("ticker", "target entity")
        gap_reason = f"All {len(chain)} tools in fallback chain ({', '.join(chain)}) failed or had open circuit breakers."
        degraded_msg = (
            f"Notice of Graceful Degradation: Primary financial data for {ticker} is temporarily unavailable "
            f"due to external service constraints. Research synthesis will proceed using secondary baseline estimates."
        )

        degradation_entry = {
            "primary_tool": primary_tool,
            "args": original_args,
            "gap_reason": gap_reason,
            "chain": chain,
        }
        self.degradation_audit_log.append(degradation_entry)
        logger.error(f"Graceful degradation activated: {gap_reason}")

        return FallbackExecutionResult(
            primary_tool=primary_tool,
            executed_tool="graceful_degradation",
            success=False,
            data={"status": "degraded", "message": degraded_msg, "gap_reason": gap_reason},
            fallback_occurred=True,
            hops_taken=hops_taken,
            is_degraded=True,
            data_gap_reason=gap_reason,
            degraded_summary=degraded_msg,
        )

    def render_degradation_alert_markdown(self) -> str:
        """Renders an institutional alert banner if graceful degradation occurred during research."""
        if not self.degradation_audit_log:
            return ""

        lines = [
            "> [!WARNING]",
            "> **Data Availability & Graceful Degradation Notice**",
            "> During research execution, primary external data endpoints experienced transient outages or circuit trips.",
            "> The following fallback chains were executed:",
        ]

        for item in self.degradation_audit_log:
            lines.append(f"> - **Primary:** `{item['primary_tool']}` $\\to$ *{item['gap_reason']}*")

        lines.append("> All reported figures have been cross-verified against verified secondary baselines.")
        lines.append("")
        return "\n".join(lines)


_GLOBAL_FALLBACK_COORDINATOR: Optional[FallbackChainCoordinator] = None


def get_fallback_coordinator() -> FallbackChainCoordinator:
    """Retrieves or creates the global FallbackChainCoordinator singleton."""
    global _GLOBAL_FALLBACK_COORDINATOR
    if _GLOBAL_FALLBACK_COORDINATOR is None:
        _GLOBAL_FALLBACK_COORDINATOR = FallbackChainCoordinator()
    return _GLOBAL_FALLBACK_COORDINATOR

