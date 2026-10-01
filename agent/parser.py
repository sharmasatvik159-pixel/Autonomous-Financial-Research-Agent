"""Response Parser for ARA-1.

Extracts reasoning traces (Thought), tool invocations (Action & Action Input),
and termination reports (Final Answer) from LLM responses with fault-tolerant regex
and JSON sanitization.
"""

from __future__ import annotations
import json
import re
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field

class AgentAction(BaseModel):
    """Represents a parsed tool invocation request from the agent."""
    tool: str = Field(description="Name of the tool to execute")
    tool_input: Dict[str, Any] = Field(default_factory=dict, description="Keyword arguments for the tool")
    thought: str = Field(default="", description="The LLM's preceding reasoning thought")

class AgentFinish(BaseModel):
    """Represents the agent's completed research output and termination signal."""
    return_values: Dict[str, Any] = Field(description="Final output dictionary containing 'output' text")
    thought: str = Field(default="", description="The concluding thought step")

class PlanOutput(BaseModel):
    """Represents a decomposed research plan from the Planner."""
    thought: str = ""
    target_ticker: str = ""
    plan: List[str] = Field(default_factory=list)

class ReActOutputParser:
    """Parser for Thought-Action-Observation textual loops and structured tool calls."""

    THOUGHT_PATTERN = re.compile(r"Thought:\s*(.*?)(?=(?:Action:|Final Answer:|$))", re.DOTALL | re.IGNORECASE)
    ACTION_PATTERN = re.compile(r"Action:\s*([a-zA-Z0-9_\-]+)", re.IGNORECASE)
    ACTION_INPUT_PATTERN = re.compile(r"Action Input:\s*(\{.*?\}|\[.*?\]|\"[^\"]*\"|[^\n\r]+)", re.DOTALL | re.IGNORECASE)
    FINAL_ANSWER_PATTERN = re.compile(r"Final Answer:\s*(.*)", re.DOTALL | re.IGNORECASE)

    @classmethod
    def parse(
        cls,
        text: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None
    ) -> Union[AgentAction, AgentFinish]:
        """Parses an LLM response string or native tool calls into AgentAction or AgentFinish."""

        if tool_calls and len(tool_calls) > 0:
            primary_call = tool_calls[0]
            thought = text.strip() if text else "Invoking tool call."
            args = primary_call.get("args", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"query": args}
            return AgentAction(
                tool=primary_call.get("name", "unknown"),
                tool_input=args,
                thought=thought,
            )

        text_cleaned = text.strip()

        final_match = cls.FINAL_ANSWER_PATTERN.search(text_cleaned)
        if final_match:
            thought_match = cls.THOUGHT_PATTERN.search(text_cleaned)
            thought = thought_match.group(1).strip() if thought_match else ""
            final_content = final_match.group(1).strip()
            return AgentFinish(
                return_values={"output": final_content},
                thought=thought
            )

        action_match = cls.ACTION_PATTERN.search(text_cleaned)
        if action_match:
            tool_name = action_match.group(1).strip()
            
            thought_match = cls.THOUGHT_PATTERN.search(text_cleaned)
            thought = thought_match.group(1).strip() if thought_match else ""

            tool_input = {}
            input_match = re.search(r"Action Input:\s*", text_cleaned, re.IGNORECASE)
            if input_match:
                rest = text_cleaned[input_match.end():].strip()
                rest = re.sub(r"^```(?:json)?\s*", "", rest)
                
                raw_input = ""
                if rest.startswith("{") or rest.startswith("["):
                    target_open = rest[0]
                    target_close = "}" if target_open == "{" else "]"
                    depth = 0
                    in_string = False
                    escape = False
                    for i, char in enumerate(rest):
                        if char == '"' and not escape:
                            in_string = not in_string
                        elif char == '\\' and in_string:
                            escape = not escape
                            continue
                        elif not in_string:
                            if char == target_open:
                                depth += 1
                            elif char == target_close:
                                depth -= 1
                                if depth == 0:
                                    raw_input = rest[:i + 1]
                                    break
                        escape = False
                    if not raw_input:
                        raw_input = rest.splitlines()[0] if rest else ""
                else:
                    raw_input = rest.splitlines()[0].strip() if rest else ""

                raw_input = re.sub(r"\s*```$", "", raw_input).strip()

                try:
                    tool_input = json.loads(raw_input)
                except json.JSONDecodeError:
                    if raw_input.startswith("{") and raw_input.endswith("}"):
                        try:
                            fixed_input = raw_input.replace("'", '"')
                            tool_input = json.loads(fixed_input)
                        except Exception:
                            tool_input = {"query": raw_input}
                    else:
                        tool_input = {"query": raw_input.strip("\"'")}

            return AgentAction(
                tool=tool_name,
                tool_input=tool_input if isinstance(tool_input, dict) else {"input": tool_input},
                thought=thought,
            )

        return AgentFinish(
            return_values={"output": text_cleaned},
            thought="Direct response provided without explicit Action."
        )

    @classmethod
    def parse_plan(cls, text: str) -> PlanOutput:
        """Parses a Planner response into a structured PlanOutput."""
        cleaned = text.strip()
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            brace_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            json_str = brace_match.group(1) if brace_match else "{}"

        try:
            data = json.loads(json_str)
            return PlanOutput(
                thought=data.get("thought", ""),
                target_ticker=data.get("target_ticker", ""),
                plan=data.get("plan", []),
            )
        except Exception:
            steps = re.findall(r"(?:Step\s*\d+:|\d+\.)\s*([^\n\r]+)", cleaned)
            return PlanOutput(
                thought="Extracted plan via fallback pattern matching.",
                target_ticker="",
                plan=steps if steps else [cleaned]
            )
