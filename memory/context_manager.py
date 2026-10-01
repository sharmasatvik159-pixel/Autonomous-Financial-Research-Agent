"""Working Memory & Short-Term Context Manager for ARA-1.

Implements Layer 1 Working Memory:
1. Token tracking and budget enforcement against model context limits.
2. Progressive summarization: compacts verbose intermediate observations,
   raw JSON filings, and transcripts into high-density quantitative markdown tables
   while preserving exact citations, numbers, dates, and currency values.
3. Selective retention: prioritizes core objectives, system constraints, long-term
   memory context, and the most recent execution steps.
"""

from __future__ import annotations
import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

from config.settings import get_settings

logger = logging.getLogger("ARA1.ContextManager")


class ContextBudgetConfig(BaseModel):
    """Configuration for context limits and compression thresholds."""
    max_context_tokens: int = Field(default=128000, description="Nominal model context window limit")
    threshold_ratio: float = Field(default=0.65, description="Trigger progressive summarization at 65% budget")
    max_history_tokens: int = Field(default=6000, description="Target token budget for ReAct history loop")
    preserve_recent_steps: int = Field(default=2, description="Number of recent ReAct cycles to keep uncompressed")
    chars_per_token: float = Field(default=3.8, description="Average characters per token heuristic")


class ContextManager:
    """Manages working memory tokens via progressive summarization and selective retention."""

    def __init__(
        self,
        config: Optional[ContextBudgetConfig] = None,
        llm_client: Optional[Any] = None,
    ):
        self.settings = get_settings()
        limit = getattr(self.settings, "CONTEXT_WINDOW_LIMIT", 128000)
        self.config = config or ContextBudgetConfig(
            max_context_tokens=limit,
            max_history_tokens=min(6000, int(limit * 0.20))
        )
        self.llm_client = llm_client
        self.total_compressions: int = 0
        self.tokens_saved: int = 0

    def estimate_tokens(self, text: Union[str, List[str], Dict[str, Any]]) -> int:
        """Estimates token count using character heuristic or string length."""
        if isinstance(text, str):
            content = text
        elif isinstance(text, list):
            content = " ".join(str(item) for item in text)
        elif isinstance(text, dict):
            content = json.dumps(text)
        else:
            content = str(text)

        if not content:
            return 0
        return max(1, int(len(content) / self.config.chars_per_token))

    def compact_observation(self, observation: Any, max_chars: int = 1000) -> str:
        """Compacts verbose observation payloads into high-density Markdown representations."""
        if observation is None:
            return "No data returned."

        # Case 1: Structured dict or list (e.g. from financial_data_api or sec_filing)
        if isinstance(observation, dict):
            return self._format_dict_as_markdown(observation, max_chars=max_chars)
        elif isinstance(observation, list):
            return self._format_list_as_markdown(observation, max_chars=max_chars)

        text = str(observation).strip()

        # If text is JSON formatted, try parsing
        if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return self._format_dict_as_markdown(parsed, max_chars=max_chars)
                elif isinstance(parsed, list):
                    return self._format_list_as_markdown(parsed, max_chars=max_chars)
            except Exception:
                pass

        if len(text) <= max_chars:
            return text

        # Extract sentences with numbers, currencies, percentages, and dates
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        valuable_lines = []
        num_pattern = re.compile(r"(\$|%|€|£|\b\d+(?:\.\d+)?\s*(?:Billion|Million|Trillion|B|M|K)?\b)", re.IGNORECASE)

        for line in lines:
            if num_pattern.search(line) or "revenue" in line.lower() or "income" in line.lower():
                valuable_lines.append(line)

        if valuable_lines:
            compacted = "\n".join(valuable_lines)
            if len(compacted) > max_chars:
                compacted = compacted[:max_chars] + "\n... [Remaining quantitative rows truncated]"
            return f"[Compacted Quantitative Excerpt]:\n{compacted}"

        return text[:max_chars] + f"\n... [Truncated {len(text) - max_chars} characters]"

    def _format_dict_as_markdown(self, data: Dict[str, Any], max_chars: int = 1000) -> str:
        """Converts structured dictionaries into concise key-value or Markdown tables."""
        lines = []

        # If data contains annual_metrics list (financial data api format)
        if "annual_metrics" in data and isinstance(data["annual_metrics"], list):
            metrics = data["annual_metrics"]
            if metrics and isinstance(metrics[0], dict):
                cols = list(metrics[0].keys())
                header = "| " + " | ".join(cols) + " |"
                sep = "| " + " | ".join(["---"] * len(cols)) + " |"
                rows = [header, sep]
                for m in metrics:
                    row = "| " + " | ".join(str(m.get(c, "-")) for c in cols) + " |"
                    rows.append(row)
                lines.append("\n".join(rows))

        # Check for segment performance
        if "segment_performance" in data and isinstance(data["segment_performance"], dict):
            lines.append("### Segment Performance Breakdown:")
            for seg, vals in data["segment_performance"].items():
                if isinstance(vals, dict):
                    v_str = ", ".join(f"{k}: {v}" for k, v in vals.items())
                    lines.append(f"- **{seg.replace('_', ' ')}**: {v_str}")
                else:
                    lines.append(f"- **{seg.replace('_', ' ')}**: {vals}")

        # Other top-level scalars
        scalar_items = []
        for k, v in data.items():
            if k in ("annual_metrics", "segment_performance"):
                continue
            if isinstance(v, (str, int, float, bool)):
                scalar_items.append(f"- **{k.replace('_', ' ').title()}**: {v}")

        if scalar_items:
            lines.insert(0, "\n".join(scalar_items))

        result = "\n\n".join(lines) if lines else json.dumps(data, indent=2)
        if len(result) > max_chars:
            result = result[:max_chars] + "\n... [Structured table truncated]"
        return result

    def _format_list_as_markdown(self, items: List[Any], max_chars: int = 1000) -> str:
        """Converts lists into concise bullet points."""
        lines = []
        for idx, item in enumerate(items[:15], start=1):
            if isinstance(item, dict):
                # Search result format: title, url, snippet
                title = item.get("title") or item.get("headline") or f"Item {idx}"
                snippet = item.get("snippet") or item.get("content") or item.get("date") or ""
                url = item.get("url") or ""
                url_str = f" ({url})" if url else ""
                lines.append(f"{idx}. **{title}**{url_str}: {snippet[:200]}")
            else:
                lines.append(f"- {str(item)[:200]}")

        result = "\n".join(lines)
        if len(items) > 15:
            result += f"\n... [Plus {len(items) - 15} additional items omitted]"
        return result[:max_chars]

    def progressive_summarize(
        self,
        history_lines: List[str],
        preserve_recent_cycles: int = 2,
    ) -> List[str]:
        """Progressively collapses older ReAct steps into high-density Key Findings bullet points.

        Preserves:
        1. Query and context preamble
        2. Retrieved Long-Term Memory (if present)
        3. Most recent `preserve_recent_cycles` cycles (Thought, Action, Action Input, Observation)
        
        Compacts:
        Older intermediate steps into concise verified findings.
        """
        if not history_lines:
            return []

        # Identify fixed header lines (Research Query, Prior Memory)
        header_lines: List[str] = []
        step_lines: List[str] = []

        for line in history_lines:
            if line.startswith("Research Query:") or line.startswith("Retrieved Long-Term Memory:"):
                header_lines.append(line)
            else:
                step_lines.append(line)

        # Break step_lines into cycles (each cycle starts with 'Thought:')
        cycles: List[List[str]] = []
        current_cycle: List[str] = []

        for line in step_lines:
            if line.startswith("Thought:") and current_cycle:
                cycles.append(current_cycle)
                current_cycle = [line]
            else:
                current_cycle.append(line)
        if current_cycle:
            cycles.append(current_cycle)

        # If few cycles, nothing to summarize
        if len(cycles) <= preserve_recent_cycles:
            return history_lines

        # Separate older cycles from recent cycles
        older_cycles = cycles[:-preserve_recent_cycles]
        recent_cycles = cycles[-preserve_recent_cycles:]

        # Extract high-density findings from older cycles
        findings: List[str] = []
        num_pattern = re.compile(r"(\$|%|€|£|\b\d+(?:\.\d+)?\s*(?:Billion|Million|Trillion|B|M|K)?\b)", re.IGNORECASE)

        for c_idx, cycle in enumerate(older_cycles, start=1):
            action_name = "Analysis"
            action_input = ""
            for item in cycle:
                if item.startswith("Action:"):
                    action_name = item.replace("Action:", "").strip()
                elif item.startswith("Action Input:"):
                    action_input = item.replace("Action Input:", "").strip()
                elif item.startswith("Observation:"):
                    obs_body = item.replace("Observation:", "").strip()
                    # Extract quantitative facts or first key sentence
                    lines = [ln.strip() for ln in obs_body.splitlines() if ln.strip()]
                    key_metrics = [ln for ln in lines if num_pattern.search(ln)]
                    if key_metrics:
                        summary_point = f"Step {c_idx} [{action_name}]: " + " | ".join(key_metrics[:3])
                    else:
                        summary_point = f"Step {c_idx} [{action_name}]: " + (lines[0][:150] if lines else "Completed.")
                    findings.append(f"- {summary_point}")

        summary_block = (
            f"**[PROGRESSIVE SUMMARY OF EARLIER RESEARCH STEPS (Steps 1-{len(older_cycles)})]**\n"
            + "\n".join(findings)
        )

        reconstructed: List[str] = []
        reconstructed.extend(header_lines)
        reconstructed.append(summary_block)
        for cycle in recent_cycles:
            reconstructed.extend(cycle)

        self.total_compressions += 1
        initial_tokens = self.estimate_tokens(history_lines)
        new_tokens = self.estimate_tokens(reconstructed)
        self.tokens_saved += max(0, initial_tokens - new_tokens)
        logger.info(
            f"Progressive summarization executed: {initial_tokens} tokens -> {new_tokens} tokens "
            f"(saved ~{initial_tokens - new_tokens} tokens)."
        )

        return reconstructed

    def manage_context(
        self,
        history_lines: List[str],
        force_summary: bool = False,
    ) -> List[str]:
        """Monitors working token usage and applies compaction/summarization if budget exceeded."""
        current_tokens = self.estimate_tokens(history_lines)

        # Check if history exceeds threshold
        if not force_summary and current_tokens <= self.config.max_history_tokens:
            return history_lines

        logger.warning(
            f"Working memory token count ({current_tokens}) exceeded budget threshold "
            f"({self.config.max_history_tokens}). Invoking progressive summarization."
        )

        # Step 1: Progressive summarization of older cycles
        compacted_history = self.progressive_summarize(
            history_lines,
            preserve_recent_cycles=self.config.preserve_recent_steps
        )

        # Step 2: If still exceeds budget, aggressively compact recent observations
        new_token_count = self.estimate_tokens(compacted_history)
        if new_token_count > self.config.max_history_tokens:
            logger.info("Applying secondary selective observation compaction.")
            pruned: List[str] = []
            for item in compacted_history:
                if item.startswith("Observation:"):
                    raw_obs = item.replace("Observation:", "").strip()
                    compact_obs = self.compact_observation(raw_obs, max_chars=600)
                    pruned.append(f"Observation: {compact_obs}")
                else:
                    pruned.append(item)
            return pruned

        return compacted_history

    def get_metrics(self) -> Dict[str, Any]:
        """Returns working memory accounting metrics."""
        return {
            "total_compressions": self.total_compressions,
            "estimated_tokens_saved": self.tokens_saved,
            "max_history_budget": self.config.max_history_tokens,
            "context_window_limit": self.config.max_context_tokens,
        }
