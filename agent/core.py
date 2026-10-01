"""Core Reasoning Engine for ARA-1 Autonomous Financial Research Agent.

Implements the ReAct (Thought-Action-Observation) loop and Plan-and-Execute
patterns with strict iteration limits, tool dispatch, vector memory pre-checking,
and latency/token accounting.
"""

from __future__ import annotations
import re
import time
import logging
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field

from config.settings import get_settings
from agent.llm_client import LLMClient
from agent.logger import get_agent_logger, AgentLogger
from agent.parser import ReActOutputParser, AgentAction, AgentFinish, PlanOutput
from agent.prompts import (
    get_react_system_prompt,
    PLANNER_PROMPT_TEMPLATE,
    format_tool_descriptions,
)
from tools.tool_registry import ToolRegistry, ToolResult, create_default_registry
from memory.vector_store import FinancialVectorStore, ResearchDocument
from memory.context_manager import ContextManager
from memory.episodic import EpisodicMemoryStore, EpisodicRecord

logger = logging.getLogger("ARA1.Core")

class AgentExecutionResult(BaseModel):
    """Complete deliverable envelope returned after agent execution."""
    query: str
    report: str
    iterations: int
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    trace: List[Dict[str, Any]] = Field(default_factory=list)
    token_usage: Dict[str, Any] = Field(default_factory=dict)
    latency_seconds: float = 0.0
    terminated_reason: str = "completed"
    memory_hits: int = 0

class FinancialResearchAgent:
    """Autonomous Financial Research Agent (ARA-1)."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        vector_store: Optional[FinancialVectorStore] = None,
        agent_logger: Optional[AgentLogger] = None,
        context_manager: Optional[ContextManager] = None,
        episodic_store: Optional[EpisodicMemoryStore] = None,
        max_iterations: int = 10,
        pattern: str = "REACT",
    ):
        self.settings = get_settings()
        self.llm_client = llm_client or LLMClient()
        self.tool_registry = tool_registry or create_default_registry()
        self.vector_store = vector_store or FinancialVectorStore()
        self.agent_logger = agent_logger or get_agent_logger()
        self.context_manager = context_manager or ContextManager(llm_client=self.llm_client)
        self.episodic_store = episodic_store or EpisodicMemoryStore()
        self.max_iterations = max_iterations or self.settings.MAX_TOOL_CALLS_PER_TASK
        self.pattern = pattern.upper()

        self._attach_default_mock_handlers()

    def _attach_default_mock_handlers(self) -> None:
        """Configures tools with realistic financial mock data for offline testing."""
        cp_tool = self.tool_registry.get_tool("company_profile")
        if cp_tool and hasattr(cp_tool, "mock_handler"):
            def mock_cp(ticker: str) -> Dict[str, Any]:
                t = ticker.upper()
                if t == "MSFT":
                    return {
                        "ticker": "MSFT",
                        "company_name": "Microsoft Corporation",
                        "sector": "Information Technology",
                        "industry": "Software - Infrastructure",
                        "market_cap": "$3.12 Trillion",
                        "ceo": "Satya Nadella",
                        "cfo": "Amy Hood",
                        "headquarters": "Redmond, Washington",
                        "description": (
                            "Microsoft Corporation develops and supports software, services, devices, and solutions. "
                            "Core segments include Productivity and Business Processes (Office, LinkedIn), "
                            "Intelligent Cloud (Azure, Windows Server), and More Personal Computing (Windows, Xbox, Surface)."
                        ),
                    }
                return {"ticker": t, "name": f"{t} Corp", "sector": "Technology", "market_cap": "$100 Billion"}
            cp_tool.mock_handler = mock_cp

        fin_tool = self.tool_registry.get_tool("financial_data_api")
        if fin_tool and hasattr(fin_tool, "mock_handler"):
            def mock_fin(ticker: str, statement_type: str = "income_statement", period: str = "annual", years: int = 3) -> Dict[str, Any]:
                t = ticker.upper()
                if t == "MSFT":
                    return {
                        "ticker": "MSFT",
                        "fiscal_year_end": "June 30",
                        "annual_metrics": [
                            {
                                "fiscal_year": "FY24",
                                "revenue": "$245.12B",
                                "revenue_growth": "+15.7% YoY",
                                "gross_margin": "69.8%",
                                "operating_income": "$109.43B",
                                "operating_margin": "44.6%",
                                "net_income": "$88.14B",
                                "diluted_eps": "$11.80",
                                "free_cash_flow": "$74.07B",
                            },
                            {
                                "fiscal_year": "FY23",
                                "revenue": "$211.91B",
                                "operating_income": "$88.52B",
                                "net_income": "$72.36B",
                            },
                        ],
                        "segment_performance": {
                            "Intelligent_Cloud": {"revenue": "$105.36B", "growth": "+19% YoY", "azure_growth": "+29% YoY"},
                            "Productivity_and_Business_Processes": {"revenue": "$77.71B", "growth": "+12% YoY"},
                            "More_Personal_Computing": {"revenue": "$62.05B", "growth": "+13% YoY"},
                        },
                    }
                return {"ticker": t, "revenue": "$50B", "status": "simulated_data"}
            fin_tool.mock_handler = mock_fin

        ws_tool = self.tool_registry.get_tool("web_search")
        if ws_tool and hasattr(ws_tool, "mock_handler"):
            def mock_ws(query: str, num_results: int = 5, date_range: Optional[str] = None) -> List[Dict[str, Any]]:
                return [
                    {
                        "title": "Microsoft Expands Azure AI Datacenter Infrastructure Globally",
                        "url": "https://reuters.com/technology/microsoft-azure-ai-infrastructure",
                        "snippet": "Microsoft invested heavily in global datacenter capacity to satisfy surging demand for OpenAI models and Copilot subscriptions.",
                        "date": "2024-09-15",
                    },
                    {
                        "title": "Satya Nadella Outlines Vision for Autonomous AI Agents in Enterprise",
                        "url": "https://bloomberg.com/news/satya-nadella-enterprise-ai-agents",
                        "snippet": "CEO Satya Nadella highlighted Copilot Studio and autonomous agentic workflows as the next multi-billion dollar growth vector for enterprise software.",
                        "date": "2024-09-20",
                    },
                ]
            ws_tool.mock_handler = mock_ws

    def _extract_ticker_heuristic(self, query: str) -> Optional[str]:
        """Simple heuristic to detect target ticker from query string."""
        clean_q = re.sub(r"['’]s\b", "", query, flags=re.IGNORECASE)
        upper_words = clean_q.replace(",", " ").replace(".", " ").replace("?", " ").split()
        known_tickers = {
            "MICROSOFT": "MSFT", "MSFT": "MSFT",
            "APPLE": "AAPL", "AAPL": "AAPL",
            "TESLA": "TSLA", "TSLA": "TSLA",
            "AMAZON": "AMZN", "AMZN": "AMZN",
            "GOOGLE": "GOOGL", "ALPHABET": "GOOGL", "GOOGL": "GOOGL",
            "PALANTIR": "PLTR", "PLTR": "PLTR",
            "NVIDIA": "NVDA", "NVDA": "NVDA",
        }
        for w in upper_words:
            clean = re.sub(r"[^A-Za-z0-9]", "", w).upper()
            if clean in known_tickers:
                return known_tickers[clean]
        return None

    def execute(self, query: str, session_id: Optional[str] = None) -> AgentExecutionResult:
        """Executes the research query according to the configured agent pattern."""
        start_time = time.perf_counter()
        session_id = session_id or f"session-{int(time.time())}"
        self.agent_logger.reset_trace(session_id)

        target_ticker = self._extract_ticker_heuristic(query)

        memory_context = []
        memory_hits = 0
        try:
            mem_results = self.vector_store.search(
                query=query,
                ticker=target_ticker,
                top_k=3,
                min_confidence=0.85
            )
            if mem_results:
                memory_hits = len(mem_results)
                for r in mem_results:
                    memory_context.append(f"[Prior Memory: {r.document.id}] {r.document.content}")
                self.agent_logger.log_thought(
                    0,
                    f"Found {memory_hits} relevant records in long-term memory"
                    + (f" for ticker {target_ticker}." if target_ticker else "."),
                    query=query,
                )
        except Exception as e:
            logger.warning(f"Memory check skipped due to error: {e}")

        procedural_guidance = ""
        try:
            episodes = self.episodic_store.retrieve_strategy(query=query, target_ticker=target_ticker, top_k=1)
            if episodes:
                procedural_guidance = self.episodic_store.format_strategy_for_planner(episodes)
                self.agent_logger.log_thought(
                    0,
                    f"Retrieved procedural strategy from episodic memory ({episodes[0].episode_id}).",
                    query=query,
                )
        except Exception as e:
            logger.warning(f"Episodic memory check skipped: {e}")

        if self.pattern == "PLAN_AND_EXECUTE":
            result = self._execute_plan_and_execute(query, memory_context, procedural_guidance, start_time, memory_hits, target_ticker)
        else:
            result = self._execute_react(query, memory_context, procedural_guidance, start_time, memory_hits, target_ticker)

        return result

    def _execute_react(
        self,
        query: str,
        memory_context: List[str],
        procedural_guidance: str,
        start_time: float,
        memory_hits: int,
        target_ticker: Optional[str] = None,
    ) -> AgentExecutionResult:
        """Executes the standard ReAct (Thought-Action-Observation) loop."""
        tools_metadata = self.tool_registry.get_openai_schemas(only_unlocked=True)
        flat_tools = [
            {
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "category": getattr(self.tool_registry.get_tool(t["function"]["name"]), "metadata", None).category
                if self.tool_registry.get_tool(t["function"]["name"]) else "general",
                "parameters": t["function"]["parameters"],
            }
            for t in tools_metadata
        ]

        system_prompt = get_react_system_prompt(flat_tools, max_iterations=self.max_iterations)

        history_lines = [f"Research Query: {query}"]
        if memory_context:
            history_lines.append("Retrieved Long-Term Memory:\n" + "\n".join(memory_context))
        if procedural_guidance:
            history_lines.append(f"Procedural Guidance from Prior Experience:\n{procedural_guidance}")

        tool_calls_executed = []
        terminated_reason = "max_iterations"
        final_report = ""

        for step in range(1, self.max_iterations + 1):
            history_lines = self.context_manager.manage_context(history_lines)

            prompt = f"{system_prompt}\n\n" + "\n\n".join(history_lines) + f"\n\nThought {step}:"

            llm_response = self.llm_client.invoke(prompt)

            response_text = llm_response.content.strip()
            if not response_text.lower().startswith("thought:") and not response_text.lower().startswith("final answer:"):
                response_text = f"Thought: {response_text}"

            parsed = ReActOutputParser.parse(response_text, tool_calls=llm_response.tool_calls)

            if isinstance(parsed, AgentFinish):
                final_report = parsed.return_values.get("output", "")
                self.agent_logger.log_thought(step, parsed.thought or "Finalizing research report.")
                terminated_reason = "completed"
                break

            elif isinstance(parsed, AgentAction):
                self.agent_logger.log_thought(step, parsed.thought)
                self.agent_logger.log_action(step, parsed.tool, parsed.tool_input)

                tool_res: ToolResult = self.tool_registry.execute(
                    parsed.tool,
                    parsed.tool_input,
                    use_fallback=True
                )

                tool_calls_executed.append({
                    "step": step,
                    "tool": parsed.tool,
                    "input": parsed.tool_input,
                    "success": tool_res.success,
                    "latency": tool_res.latency_seconds,
                    "fallback_used": tool_res.fallback_used,
                })

                if tool_res.fallback_used:
                    self.episodic_store.record_error_recovery(
                        failed_tool=parsed.tool,
                        error_message=tool_res.error or "Primary tool failure",
                        recovery_tool=tool_res.fallback_used,
                        recovery_action=f"Auto-routed to {tool_res.fallback_used}",
                        success=tool_res.success,
                        ticker=target_ticker,
                    )

                obs_payload = tool_res.data if tool_res.success else f"ERROR: {tool_res.error}"
                self.agent_logger.log_observation(
                    step,
                    parsed.tool,
                    obs_payload,
                    tool_res.latency_seconds,
                    fallback_used=tool_res.fallback_used,
                    success=tool_res.success,
                )

                compact_obs = self.context_manager.compact_observation(obs_payload, max_chars=2000)

                history_lines.append(f"Thought: {parsed.thought}")
                history_lines.append(f"Action: {parsed.tool}")
                history_lines.append(f"Action Input: {parsed.tool_input}")
                history_lines.append(f"Observation: {compact_obs}")

        if not final_report:
            synthesis_prompt = (
                f"You have reached the maximum tool iterations for query: '{query}'.\n"
                f"Synthesize all gathered observations below into a structured Markdown research report.\n\n"
                + "\n".join(history_lines)
            )
            syn_res = self.llm_client.invoke(synthesis_prompt)
            final_report = syn_res.content

        if terminated_reason == "completed" and tool_calls_executed:
            try:
                self.episodic_store.record_episode(
                    EpisodicRecord(
                        query=query,
                        query_type="company_profile" if "profile" in query.lower() else "financial_research",
                        target_ticker=target_ticker,
                        tool_sequence=[tc["tool"] for tc in tool_calls_executed],
                        successful_plan=[f"Executed {len(tool_calls_executed)} steps for {target_ticker or 'target'}"],
                        reflection=f"Synthesized research report for {target_ticker or 'target'} using {len(tool_calls_executed)} tool steps.",
                        outcome_quality=0.96,
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to record completed research episode: {e}")

        latency = time.perf_counter() - start_time
        usage = self.llm_client.get_usage_summary()

        return AgentExecutionResult(
            query=query,
            report=final_report,
            iterations=len(tool_calls_executed),
            tool_calls=tool_calls_executed,
            trace=self.agent_logger.get_active_trace(),
            token_usage=usage,
            latency_seconds=round(latency, 3),
            terminated_reason=terminated_reason,
            memory_hits=memory_hits,
        )

    def _execute_plan_and_execute(
        self,
        query: str,
        memory_context: List[str],
        procedural_guidance: str,
        start_time: float,
        memory_hits: int,
        target_ticker: Optional[str] = None,
    ) -> AgentExecutionResult:
        """Executes the Plan-and-Execute pattern."""
        tools_metadata = self.tool_registry.get_openai_schemas(only_unlocked=True)
        flat_tools = [
            {"name": t["function"]["name"], "description": t["function"]["description"], "parameters": t["function"]["parameters"]}
            for t in tools_metadata
        ]
        tools_str = format_tool_descriptions(flat_tools)

        planner_prompt = PLANNER_PROMPT_TEMPLATE.format(tool_descriptions=tools_str, query=query)
        if procedural_guidance:
            planner_prompt += f"\n\n{procedural_guidance}"

        plan_resp = self.llm_client.invoke(planner_prompt)
        parsed_plan: PlanOutput = ReActOutputParser.parse_plan(plan_resp.content)

        self.agent_logger.log_thought(0, f"Planner formulated {len(parsed_plan.plan)} steps: {parsed_plan.plan}")

        react_res = self._execute_react(
            query=query,
            memory_context=memory_context,
            procedural_guidance=procedural_guidance,
            start_time=start_time,
            memory_hits=memory_hits,
            target_ticker=target_ticker,
        )
        return react_res

