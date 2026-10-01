"""Unit tests for Core Financial Research Agent (ReAct and Plan-and-Execute)."""

import pytest
from agent.core import FinancialResearchAgent, AgentExecutionResult
from agent.llm_client import LLMClient, MockChatModel
from agent.parser import ReActOutputParser, AgentAction, AgentFinish, PlanOutput
from tools.tool_registry import create_default_registry


def test_parser_extracts_action():
    """Verify parser extracts thought, tool name, and JSON input."""
    text = (
        "Thought: I need to pull the company profile for Tesla.\n"
        "Action: company_profile\n"
        "Action Input: {\"ticker\": \"TSLA\"}"
    )
    parsed = ReActOutputParser.parse(text)
    assert isinstance(parsed, AgentAction)
    assert parsed.tool == "company_profile"
    assert parsed.tool_input == {"ticker": "TSLA"}
    assert "Tesla" in parsed.thought


def test_parser_extracts_final_answer():
    """Verify parser extracts thought and final report."""
    text = (
        "Thought: I have gathered all necessary information.\n"
        "Final Answer: # Apple Inc. Profile\nApple generated $383B in revenue."
    )
    parsed = ReActOutputParser.parse(text)
    assert isinstance(parsed, AgentFinish)
    assert "Apple Inc. Profile" in parsed.return_values["output"]
    assert "gathered all necessary" in parsed.thought


def test_agent_execution_with_mock_tools():
    """Verify agent completes a reasoning loop with mock tools."""
    # Custom mock model that produces an Action then Final Answer
    class TwoStepMock(MockChatModel):
        def __init__(self):
            super().__init__()
            self.count = 0

        def invoke(self, messages, tools=None):
            self.count += 1
            if self.count == 1:
                content = (
                    "Thought: Retrieve Microsoft profile.\n"
                    "Action: company_profile\n"
                    "Action Input: {\"ticker\": \"MSFT\"}"
                )
            else:
                content = (
                    "Thought: Synthesis complete.\n"
                    "Final Answer: # Microsoft Profile\nSummary."
                )
            from langchain_core.messages import AIMessage
            return AIMessage(content=content)

    llm = LLMClient(force_mock=True)
    llm._chat_model = TwoStepMock()

    agent = FinancialResearchAgent(
        llm_client=llm,
        tool_registry=create_default_registry(),
        max_iterations=5,
    )

    result = agent.execute("Analyze Microsoft Corporation")
    assert isinstance(result, AgentExecutionResult)
    assert result.terminated_reason == "completed"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["tool"] == "company_profile"
    assert "# Microsoft Profile" in result.report


def test_agent_strict_iteration_limit():
    """Verify agent terminates when maximum iteration limit is reached."""
    # Mock model that loops indefinitely requesting tools
    class InfiniteMock(MockChatModel):
        def invoke(self, messages, tools=None):
            from langchain_core.messages import AIMessage
            return AIMessage(
                content=(
                    "Thought: Keep searching for more news.\n"
                    "Action: web_search\n"
                    "Action Input: {\"query\": \"tech news\"}"
                )
            )

    llm = LLMClient(force_mock=True)
    llm._chat_model = InfiniteMock()

    agent = FinancialResearchAgent(
        llm_client=llm,
        tool_registry=create_default_registry(),
        max_iterations=3,  # Strict cap
    )

    result = agent.execute("Continuous tech research")
    assert result.iterations == 3
    assert result.terminated_reason == "max_iterations"
    assert len(result.tool_calls) == 3
