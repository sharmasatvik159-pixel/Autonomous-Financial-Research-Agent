"""Comprehensive Audit Script for Tool Registry & API Integration.

Verifies:
1. Registration and presence of all 10+ core tools.
2. OpenAI and Anthropic function calling schema compliance.
3. Safe execution of all tools with valid inputs returning valid JSON data.
4. Error handling without unhandled exceptions.
"""

from __future__ import annotations
import sys
import os
import json
import pytest
from typing import Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.tool_registry import create_default_registry, ToolRegistry, ToolResult


CORE_TOOLS = [
    "sec_filing_search",
    "financial_data_api",
    "web_search",
    "news_sentiment",
    "earnings_transcript",
    "company_profile",
    "peer_comparison",
    "calculation_engine",
    "fact_checker",
    "report_generator",
    "vector_db_search",
    "vector_db_store",
]

SAMPLE_INPUTS: Dict[str, Dict[str, Any]] = {
    "sec_filing_search": {
        "ticker": "MSFT",
        "filing_type": "10-K",
        "year": 2024,
    },
    "financial_data_api": {
        "ticker": "MSFT",
        "statement_type": "income_statement",
        "period": "annual",
        "years": 3,
    },
    "web_search": {
        "query": "Microsoft Cloud revenue FY24",
        "num_results": 3,
    },
    "news_sentiment": {
        "query": "Apple Inc",
        "num_articles": 3,
        "lookback_days": 14,
    },
    "earnings_transcript": {
        "ticker": "AAPL",
        "quarter": "Q4",
        "year": 2024,
    },
    "company_profile": {
        "ticker": "MSFT",
    },
    "peer_comparison": {
        "ticker": "MSFT",
        "num_peers": 3,
    },
    "calculation_engine": {
        "calculation_type": "dcf",
        "inputs": {
            "cash_flows": [100.0, 115.0, 130.0],
            "discount_rate": 0.09,
            "terminal_growth": 0.025,
        },
    },
    "fact_checker": {
        "claim": "Microsoft FY24 total revenue reached $245.12B",
        "sources": ["SEC 10-K"],
    },
    "report_generator": {
        "template": "standard_research_report",
        "sections": {
            "Executive Summary": "MSFT delivered strong FY24 earnings.",
            "Financial Analysis": "Revenue expanded +15.7% YoY.",
        },
        "sources": ["SEC Form 10-K (2024)"],
    },
    "vector_db_store": {
        "content": "Microsoft Azure generated over $105B in Intelligent Cloud revenue in FY24.",
        "metadata": {
            "ticker": "MSFT",
            "source_type": "sec_10k",
            "confidence": 1.0,
            "verified": True,
        },
    },
    "vector_db_search": {
        "query": "Microsoft Azure revenue growth",
        "top_k": 3,
    },
}


@pytest.fixture(scope="module")
def registry() -> ToolRegistry:
    return create_default_registry()


def test_core_tools_registered(registry: ToolRegistry):
    """Verify all core tools exist in the default registry."""
    registered = registry.list_tools()
    for tool_name in CORE_TOOLS:
        assert tool_name in registered, f"Tool '{tool_name}' missing from ToolRegistry"


@pytest.mark.parametrize("tool_name", CORE_TOOLS)
def test_openai_tool_schema_conformance(registry: ToolRegistry, tool_name: str):
    """Verify that each tool schema conforms to OpenAI function calling specifications."""
    tool = registry.get_tool(tool_name)
    assert tool is not None, f"Tool '{tool_name}' not found"

    schema = tool.to_openai_schema()
    assert isinstance(schema, dict), "OpenAI schema must be a dict"
    assert schema.get("type") == "function", "OpenAI schema type must be 'function'"
    assert "function" in schema, "OpenAI schema must have 'function' key"

    fn = schema["function"]
    assert fn.get("name") == tool_name, f"Function name mismatch: {fn.get('name')} != {tool_name}"
    assert isinstance(fn.get("description"), str) and len(fn["description"]) > 0, "Description required"
    assert "parameters" in fn, "Function parameters key required"

    params = fn["parameters"]
    assert isinstance(params, dict), "Parameters must be a dict"
    assert params.get("type") == "object", "Parameters type must be 'object'"
    assert "properties" in params, "Parameters properties dict required"
    assert isinstance(params["properties"], dict), "Properties must be a dict"
    assert "required" in params and isinstance(params["required"], list), "Required field list must exist"


@pytest.mark.parametrize("tool_name", CORE_TOOLS)
def test_anthropic_tool_schema_conformance(registry: ToolRegistry, tool_name: str):
    """Verify that each tool schema conforms to Anthropic tool use specifications."""
    tool = registry.get_tool(tool_name)
    assert tool is not None, f"Tool '{tool_name}' not found"

    schema = tool.to_anthropic_schema()
    assert isinstance(schema, dict), "Anthropic schema must be a dict"
    assert schema.get("name") == tool_name, f"Tool name mismatch: {schema.get('name')} != {tool_name}"
    assert isinstance(schema.get("description"), str) and len(schema["description"]) > 0
    assert "input_schema" in schema, "Anthropic schema must have 'input_schema'"

    input_schema = schema["input_schema"]
    assert isinstance(input_schema, dict), "input_schema must be a dict"
    assert input_schema.get("type") == "object", "input_schema type must be 'object'"
    assert "properties" in input_schema, "input_schema properties dict required"


@pytest.mark.parametrize("tool_name", CORE_TOOLS)
def test_tool_execution_returns_valid_json(registry: ToolRegistry, tool_name: str):
    """Verify each tool executes safely and returns JSON-serializable data without throwing unhandled exceptions."""
    inputs = SAMPLE_INPUTS[tool_name]
    try:
        result = registry.execute(tool_name, inputs)
    except Exception as exc:
        pytest.fail(f"Unhandled exception during registry.execute('{tool_name}'): {exc}")

    assert isinstance(result, ToolResult), f"Expected ToolResult instance, got {type(result)}"
    assert result.tool_name == tool_name
    assert result.latency_seconds >= 0.0

    # Test full JSON serializability of data and envelope
    try:
        serialized = json.dumps(result.model_dump(), default=str)
        assert len(serialized) > 0
        parsed = json.loads(serialized)
        assert parsed["tool_name"] == tool_name
    except Exception as exc:
        pytest.fail(f"Tool '{tool_name}' returned non-JSON-serializable output: {exc}")


def run_full_tool_audit() -> Dict[str, Any]:
    """Autonomous standalone audit execution returning structured audit summary."""
    print("=" * 70)
    print("ARA-1 COMPREHENSIVE TOOL REGISTRY & API INTEGRATION AUDIT")
    print("=" * 70)

    reg = create_default_registry()
    audit_results = {}
    passed_count = 0
    total_count = len(CORE_TOOLS)

    for tool_name in CORE_TOOLS:
        print(f"\n[*] Auditing Tool: {tool_name}...")
        tool = reg.get_tool(tool_name)
        if not tool:
            print(f"    [-] Registration Check: FAILED (Not found)")
            audit_results[tool_name] = {"registered": False, "pass": False}
            continue

        # 1. Schema checks
        openai_schema = tool.to_openai_schema()
        anthropic_schema = tool.to_anthropic_schema()
        schema_valid = (
            openai_schema.get("type") == "function"
            and "properties" in openai_schema.get("function", {}).get("parameters", {})
            and "input_schema" in anthropic_schema
        )
        print(f"    [+] Schemas (OpenAI & Anthropic): {'VALID' if schema_valid else 'INVALID'}")

        # 2. Execution check
        inputs = SAMPLE_INPUTS[tool_name]
        try:
            res = reg.execute(tool_name, inputs)
            json_str = json.dumps(res.model_dump(), default=str)
            exec_pass = True
            print(f"    [+] Execution: SUCCESS (Latency: {res.latency_seconds:.3f}s, Success: {res.success})")
            print(f"    [+] JSON Serialization: VALID ({len(json_str)} bytes)")
        except Exception as exc:
            exec_pass = False
            print(f"    [-] Execution: CRASHED ({exc})")

        overall_pass = schema_valid and exec_pass
        if overall_pass:
            passed_count += 1

        audit_results[tool_name] = {
            "registered": True,
            "schema_valid": schema_valid,
            "execution_pass": exec_pass,
            "category": tool.metadata.category,
            "rate_limit_rps": tool.metadata.rate_limit_rps,
            "pass": overall_pass,
        }

    print("\n" + "=" * 70)
    print(f"AUDIT SUMMARY: {passed_count}/{total_count} Tools Passed Fully ({passed_count/total_count*100:.1f}%)")
    print("=" * 70)
    return audit_results


if __name__ == "__main__":
    results = run_full_tool_audit()
