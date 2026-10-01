"""Episodic Memory Store for ARA-1 (Layer 3 Procedural Learning).

Implements Layer 3 of the Three-Layer Memory Architecture:
1. Records query-strategy-outcome tuples and successful plan sequences.
2. Tracks tool call strategies, citation yields, and error recovery trajectories.
3. Retrieves relevant past strategies to prime Planner and ReAct reasoning engines,
   preventing recurring mistakes and optimizing multi-step tool execution.
"""

from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from config.settings import get_settings
from memory.vector_store import EmbeddingGenerator

logger = logging.getLogger("ARA1.EpisodicMemory")


class ErrorRecoveryPath(BaseModel):
    """Encapsulates a runtime tool failure and its successful resolution route."""
    failed_tool: str
    error_message: str
    recovery_tool: str
    recovery_action: str
    success: bool = True
    context_hint: str = ""


class EpisodicRecord(BaseModel):
    """Schema for a historical research episode and its procedural learning."""
    episode_id: str = Field(default_factory=lambda: f"ep-{uuid.uuid4().hex[:8]}")
    query: str
    query_type: str = Field(
        default="general_research",
        description="Category: 'company_profile', 'earnings_analysis', 'valuation', 'regulatory', 'macro'"
    )
    target_ticker: Optional[str] = None
    tool_sequence: List[str] = Field(default_factory=list, description="Ordered sequence of executed tools")
    successful_plan: List[str] = Field(default_factory=list, description="Plan steps that led to success")
    error_recovery_paths: List[ErrorRecoveryPath] = Field(default_factory=list)
    reflection: str = Field(
        default="",
        description="Key procedural lesson learned (e.g. 'Use 10-K Item 7 before web search for revenue')"
    )
    outcome_quality: float = Field(default=0.90, ge=0.0, le=1.0)
    citation_count: int = Field(default=0)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EpisodicMemoryStore:
    """Manages persistence and semantic/heuristic retrieval of research strategies and error recovery paths."""

    def __init__(self, persist_path: Optional[str] = None):
        self.settings = get_settings()
        if persist_path:
            self.file_path = Path(persist_path)
        else:
            base_dir = Path(self.settings.CHROMA_PERSIST_DIRECTORY).parent
            self.file_path = base_dir / "episodic_memory.json"

        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.records: List[EpisodicRecord] = []
        self.embedder = EmbeddingGenerator(dimension=self.settings.EMBEDDING_DIMENSION)
        self._load()

        # Seed with initial baseline domain strategies if empty
        if not self.records:
            self._seed_baseline_strategies()

    def _load(self) -> None:
        """Loads serialized episodic records from persistent disk."""
        if not self.file_path.exists():
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.records = [EpisodicRecord(**item) for item in data]
                logger.info(f"Loaded {len(self.records)} episodic records from {self.file_path}")
        except Exception as e:
            logger.warning(f"Failed to read episodic memory from {self.file_path}: {e}")

    def _save(self) -> None:
        """Persists episodic records to disk."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump([r.model_dump() for r in self.records], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save episodic memory to {self.file_path}: {e}")

    def _seed_baseline_strategies(self) -> None:
        """Seeds default domain knowledge and tool recovery patterns."""
        seeds = [
            EpisodicRecord(
                episode_id="ep-seed-profile-001",
                query="Comprehensive company profile and business segment breakdown",
                query_type="company_profile",
                target_ticker="MSFT",
                tool_sequence=["company_profile", "sec_filing_search", "financial_data_api", "web_search"],
                successful_plan=[
                    "Step 1: Fetch primary corporate entity overview and leadership via company_profile",
                    "Step 2: Retrieve SEC 10-K Item 1 Business description and segment taxonomy",
                    "Step 3: Extract latest audited annual revenue and segment performance via financial_data_api",
                    "Step 4: Search authoritative press wires for recent strategic developments and CEO vision"
                ],
                error_recovery_paths=[
                    ErrorRecoveryPath(
                        failed_tool="sec_filing_search",
                        error_message="Rate limit exceeded or timeout on SEC EDGAR",
                        recovery_tool="web_search",
                        recovery_action="Query company investor relations website or SEC archive via web_search",
                        success=True
                    )
                ],
                reflection=(
                    "For company profiles, querying company_profile first establishes CIK and sector boundaries; "
                    "combining 10-K MD&A with financial_data_api provides 100% verified segment figures."
                ),
                outcome_quality=0.98,
                citation_count=5
            ),
            EpisodicRecord(
                episode_id="ep-seed-earnings-002",
                query="Quarterly earnings analysis and guidance vs consensus",
                query_type="earnings_analysis",
                target_ticker="AAPL",
                tool_sequence=["financial_data_api", "earnings_transcript", "news_sentiment", "fact_checker"],
                successful_plan=[
                    "Step 1: Extract quarterly income statement and EPS via financial_data_api",
                    "Step 2: Analyze earnings transcript Q&A for executive commentary on margins",
                    "Step 3: Score market news sentiment post-release via news_sentiment",
                    "Step 4: Cross-reference consensus guidance claims with fact_checker"
                ],
                error_recovery_paths=[
                    ErrorRecoveryPath(
                        failed_tool="earnings_transcript",
                        error_message="Full transcript unavailable for latest quarter",
                        recovery_tool="web_search",
                        recovery_action="Search for verified earnings call summary press releases",
                        success=True
                    )
                ],
                reflection="Always pair transcript Q&A executive answers with audited quarterly revenue numbers.",
                outcome_quality=0.95,
                citation_count=4
            ),
        ]
        self.records.extend(seeds)
        self._save()

    def record_episode(self, record: EpisodicRecord) -> str:
        """Stores a new research episode and persists to disk."""
        self.records.append(record)
        self._save()
        logger.info(f"Recorded research episode '{record.episode_id}' for ticker '{record.target_ticker}'")
        return record.episode_id

    def record_error_recovery(
        self,
        failed_tool: str,
        error_message: str,
        recovery_tool: str,
        recovery_action: str,
        success: bool = True,
        context_hint: str = "",
        query: str = "",
        ticker: Optional[str] = None,
    ) -> None:
        """Quickly logs a tool failure and recovery sequence into episodic learning."""
        recovery = ErrorRecoveryPath(
            failed_tool=failed_tool,
            error_message=error_message,
            recovery_tool=recovery_tool,
            recovery_action=recovery_action,
            success=success,
            context_hint=context_hint,
        )
        # Attach to the latest matching record or create an incremental one
        for r in reversed(self.records):
            if ticker and r.target_ticker == ticker.upper():
                r.error_recovery_paths.append(recovery)
                self._save()
                return

        new_rec = EpisodicRecord(
            query=query or f"Recovery for {failed_tool}",
            query_type="error_recovery",
            target_ticker=ticker.upper() if ticker else None,
            tool_sequence=[failed_tool, recovery_tool],
            successful_plan=[f"Failover from {failed_tool} to {recovery_tool}"],
            error_recovery_paths=[recovery],
            reflection=f"Recovered from {failed_tool} failure by routing to {recovery_tool}.",
            outcome_quality=0.90 if success else 0.50,
        )
        self.record_episode(new_rec)

    def retrieve_strategy(
        self,
        query: str,
        query_type: Optional[str] = None,
        target_ticker: Optional[str] = None,
        top_k: int = 2,
    ) -> List[EpisodicRecord]:
        """Retrieves top matching past research strategies using lexical and query-type scoring."""
        if not self.records:
            return []

        scored: List[Tuple[float, EpisodicRecord]] = []
        q_words = set(query.lower().replace(",", " ").replace(".", " ").split())

        for record in self.records:
            score = 0.0

            # Match ticker
            if target_ticker and record.target_ticker:
                if target_ticker.upper() == record.target_ticker.upper():
                    score += 2.0

            # Match query_type
            if query_type and record.query_type == query_type:
                score += 1.5

            # Word overlap with historical query
            rec_words = set(record.query.lower().replace(",", " ").replace(".", " ").split())
            overlap = len(q_words.intersection(rec_words))
            score += overlap * 0.4

            # Quality weighting
            score *= record.outcome_quality

            scored.append((score, record))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    def get_recovery_recommendations(self, failed_tool: str) -> List[ErrorRecoveryPath]:
        """Looks up proven recovery paths for a specific failing tool."""
        recoveries = []
        for r in self.records:
            for rec in r.error_recovery_paths:
                if rec.failed_tool == failed_tool and rec.success:
                    recoveries.append(rec)
        return recoveries

    def format_strategy_for_planner(self, records: List[EpisodicRecord]) -> str:
        """Formats episodic memories into a prompt-injectable guidance block."""
        if not records:
            return ""

        lines = ["### Procedural Insights from Prior Research Episodes:"]
        for idx, rec in enumerate(records, start=1):
            ticker_str = f" [{rec.target_ticker}]" if rec.target_ticker else ""
            lines.append(f"**Episode {idx} ({rec.query_type}{ticker_str}):**")
            if rec.tool_sequence:
                lines.append(f"- *Recommended Tool Sequence:* `{' -> '.join(rec.tool_sequence)}`")
            if rec.reflection:
                lines.append(f"- *Key Lesson:* {rec.reflection}")
            if rec.error_recovery_paths:
                recov = rec.error_recovery_paths[0]
                lines.append(f"- *Proven Recovery:* If `{recov.failed_tool}` fails, fallback to `{recov.recovery_tool}` ({recov.recovery_action})")

        return "\n".join(lines)

    def count(self) -> int:
        """Returns total number of stored episodes."""
        return len(self.records)

    def clear(self) -> None:
        """Clears all stored episodes and resets the backing file."""
        self.records = []
        self._save()
