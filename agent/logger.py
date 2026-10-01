"""Logging and Trace Recording Infrastructure for ARA-1.

Captures agent reasoning traces (Thought-Action-Observation), LLM token usage,
tool dispatch latencies, circuit-breaker trips, and execution errors.
Outputs both human-readable console formatting and structured JSONL traces.
"""

from __future__ import annotations
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from config.settings import get_settings

try:
    from rich.console import Console
    from rich.theme import Theme
    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False

class AgentTraceEvent:
    """Represents a discrete event in the agent's reasoning trajectory."""

    def __init__(
        self,
        event_type: str,
        content: Dict[str, Any],
        step: Optional[int] = None,
        session_id: Optional[str] = None,
    ):
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.event_type = event_type
        self.step = step
        self.session_id = session_id or "default_session"
        self.content = content

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "step": self.step,
            "event_type": self.event_type,
            "content": self.content,
        }

class AgentLogger:
    """Central logging and trace capture engine."""

    def __init__(self, session_id: Optional[str] = None):
        self.settings = get_settings()
        self.session_id = session_id or f"ara1-session-{int(time.time())}"
        self.active_trace: List[AgentTraceEvent] = []

        self.logger = logging.getLogger("ARA1.Agent")
        self.logger.setLevel(getattr(logging, self.settings.LOG_LEVEL.upper(), logging.INFO))
        self.logger.propagate = False

        if not self.logger.handlers:
            self._setup_handlers()

        if _HAS_RICH:
            custom_theme = Theme({
                "info": "cyan",
                "warning": "yellow",
                "error": "bold red",
                "thought": "italic magenta",
                "action": "bold green",
                "observation": "blue",
            })
            self.console = Console(theme=custom_theme)
        else:
            self.console = None

    def _setup_handlers(self) -> None:
        """Sets up file and stream logging handlers."""
        log_dir = self.settings.get_log_dir()
        log_file = log_dir / Path(self.settings.LOG_FILE_PATH).name

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(getattr(logging, self.settings.LOG_LEVEL.upper(), logging.INFO))
        stream_handler.setFormatter(formatter)
        self.logger.addHandler(stream_handler)

    def _append_trace(self, event: AgentTraceEvent) -> None:
        """Append event to active in-memory trace and persist to JSONL."""
        self.active_trace.append(event)

        trace_path = Path(self.settings.TRACE_LOG_PATH)
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(trace_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to append to trace log: {e}")

    def log_thought(self, step: int, thought: str, query: Optional[str] = None) -> None:
        """Records an agent reasoning (Thought) step."""
        msg = f"[Step {step}] THOUGHT: {thought}"
        self.logger.info(msg)
        if self.console:
            try:
                self.console.print(f"[thought][Step {step}] THOUGHT:[/thought] {thought}")
            except Exception:
                pass

        self._append_trace(
            AgentTraceEvent(
                event_type="thought",
                step=step,
                session_id=self.session_id,
                content={"thought": thought, "query": query},
            )
        )

    def log_action(self, step: int, tool_name: str, tool_args: Dict[str, Any]) -> None:
        """Records an agent action (tool invocation) step."""
        msg = f"[Step {step}] ACTION: Invoking '{tool_name}' with args: {tool_args}"
        self.logger.info(msg)
        if self.console:
            try:
                self.console.print(
                    f"[action][Step {step}] ACTION:[/action] Invoking '{tool_name}' "
                    f"with args={json.dumps(tool_args)}"
                )
            except Exception:
                pass

        self._append_trace(
            AgentTraceEvent(
                event_type="action",
                step=step,
                session_id=self.session_id,
                content={"tool_name": tool_name, "arguments": tool_args},
            )
        )

    def log_observation(
        self,
        step: int,
        tool_name: str,
        observation: Any,
        latency_seconds: float,
        fallback_used: Optional[str] = None,
        success: bool = True,
    ) -> None:
        """Records an observation returned by a tool."""
        obs_str = str(observation)
        preview = (obs_str[:200] + "...") if len(obs_str) > 200 else obs_str
        msg = (
            f"[Step {step}] OBSERVATION ({tool_name}, {latency_seconds:.3f}s): "
            f"Success={success}, Fallback={fallback_used} -> {preview}"
        )
        self.logger.info(msg)
        if self.console:
            color = "observation" if success else "error"
            try:
                self.console.print(
                    f"[{color}][Step {step}] OBSERVATION ({tool_name} in {latency_seconds:.3f}s):[/{color}] {preview}"
                )
            except Exception:
                pass

        self._append_trace(
            AgentTraceEvent(
                event_type="observation",
                step=step,
                session_id=self.session_id,
                content={
                    "tool_name": tool_name,
                    "success": success,
                    "latency_seconds": latency_seconds,
                    "fallback_used": fallback_used,
                    "observation": observation,
                },
            )
        )

    def log_llm_call(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_seconds: float,
        estimated_cost_usd: float = 0.0,
    ) -> None:
        """Records token usage and latency for an LLM call."""
        total_tokens = prompt_tokens + completion_tokens
        msg = (
            f"LLM Call ({model}): {total_tokens} tokens "
            f"(P: {prompt_tokens}, C: {completion_tokens}) in {latency_seconds:.2f}s "
            f"~${estimated_cost_usd:.5f}"
        )
        self.logger.debug(msg)

        self._append_trace(
            AgentTraceEvent(
                event_type="llm_call",
                session_id=self.session_id,
                content={
                    "model": model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "latency_seconds": latency_seconds,
                    "cost_usd": estimated_cost_usd,
                },
            )
        )

    def log_error(self, component: str, error_message: str, exc: Optional[Exception] = None) -> None:
        """Records an execution error or failure."""
        msg = f"ERROR in {component}: {error_message}"
        self.logger.error(msg, exc_info=bool(exc))
        if self.console:
            self.console.print(f"[error]❌ ERROR ({component}):[/error] {error_message}")

        self._append_trace(
            AgentTraceEvent(
                event_type="error",
                session_id=self.session_id,
                content={"component": component, "error": error_message, "exception": str(exc) if exc else None},
            )
        )

    def get_active_trace(self) -> List[Dict[str, Any]]:
        """Returns the in-memory trace as a list of dicts."""
        return [event.to_dict() for event in self.active_trace]

    def reset_trace(self, new_session_id: Optional[str] = None) -> None:
        """Resets the current in-memory trace for a new research challenge."""
        self.active_trace = []
        if new_session_id:
            self.session_id = new_session_id

_GLOBAL_LOGGER: Optional[AgentLogger] = None

def get_agent_logger(session_id: Optional[str] = None) -> AgentLogger:
    """Singleton getter for AgentLogger."""
    global _GLOBAL_LOGGER
    if _GLOBAL_LOGGER is None:
        _GLOBAL_LOGGER = AgentLogger(session_id=session_id)
    elif session_id and _GLOBAL_LOGGER.session_id != session_id:
        _GLOBAL_LOGGER.session_id = session_id
    return _GLOBAL_LOGGER
