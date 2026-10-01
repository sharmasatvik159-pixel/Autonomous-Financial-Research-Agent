"""Unit tests for ToolRegistry and Tool implementations."""

import pytest
from tools.tool_registry import (
    ToolRegistry,
    ToolMetadata,
    BaseTool,
    ToolResult,
    MockStubTool,
    create_default_registry,
)
from tools.schemas import SecFilingSearchInput, CalculationEngineInput

def test_registry_registration_and_retrieval():
    """Verify tools can be registered, listed, and retrieved."""
    registry = create_default_registry()
    tools = registry.list_tools()

    assert len(tools) >= 12
    assert "sec_filing_search" in tools
    assert "financial_data_api" in tools
    assert "calculation_engine" in tools

    sec_tool = registry.get_tool("sec_filing_search")
    assert sec_tool is not None
    assert sec_tool.name == "sec_filing_search"
    assert sec_tool.metadata.category == "regulatory"

def test_openai_schema_generation():
    """Verify tool schemas generate valid OpenAI function specs."""
    registry = create_default_registry()
    schemas = registry.get_openai_schemas()

    assert len(schemas) >= 12
    first_schema = schemas[0]
    assert first_schema["type"] == "function"
    assert "name" in first_schema["function"]
    assert "description" in first_schema["function"]
    assert "parameters" in first_schema["function"]
    assert first_schema["function"]["parameters"]["type"] == "object"

def test_tool_execution_success():
    """Test successful tool execution with parameter validation."""
    registry = create_default_registry()
    result = registry.execute(
        "sec_filing_search",
        {"ticker": "AAPL", "filing_type": "10-K", "year": 2024}
    )

    assert result.success is True
    assert result.tool_name == "sec_filing_search"
    assert result.data is not None
    assert result.error is None
    assert result.latency_seconds >= 0.0

def test_tool_execution_schema_validation_failure():
    """Test execution fails gracefully on invalid parameters."""
    registry = create_default_registry()
    result = registry.execute(
        "sec_filing_search",
        {"ticker": "AAPL"}
    )

    assert result.success is False
    assert "validation failed" in result.error.lower()

def test_tool_lock_and_unlock():
    """Test dynamic tool unlocking mechanism (supports progression milestones)."""
    registry = create_default_registry()
    registry.lock_tool("calculation_engine")

    assert "calculation_engine" not in registry.list_tools(only_unlocked=True)

    result = registry.execute("calculation_engine", {"calculation_type": "dcf", "inputs": {}})
    assert result.success is False
    assert "locked" in result.error.lower()

    unlocked = registry.unlock_tool("calculation_engine")
    assert unlocked is True
    assert "calculation_engine" in registry.list_tools(only_unlocked=True)

def test_fallback_routing():
    """Test that a failing tool triggers fallback chain."""
    registry = ToolRegistry()

    def fail_handler(**kwargs):
        raise ConnectionError("Primary API service unavailable")

    primary = MockStubTool(
        ToolMetadata(
            name="primary_failing_api",
            description="Failing API",
            fallback_tools=["backup_working_api"],
        ),
        mock_handler=fail_handler,
    )

    backup = MockStubTool(
        ToolMetadata(
            name="backup_working_api",
            description="Backup API",
        ),
        mock_handler=lambda **kwargs: {"source": "backup_db", "data": "restored_data"},
    )

    registry.register_tool(primary)
    registry.register_tool(backup)

    res = registry.execute("primary_failing_api", {}, use_fallback=True)
    assert res.success is True
    assert res.fallback_used == "backup_working_api"
    assert res.data["source"] == "backup_db"

def test_circuit_breaker():
    """Test circuit breaker stops calls when tripped."""
    registry = create_default_registry()

    registry.set_circuit_breaker(lambda tool_name: tool_name == "web_search")

    res = registry.execute("web_search", {"query": "Tesla revenue"}, use_fallback=False)
    assert res.success is False
    assert "circuit breaker open" in res.error.lower()

def test_tool_cache_set_and_get():
    """Verify ToolCache persists and retrieves data with expiration check."""
    import tempfile, shutil
    from tools.cache import ToolCache

    tmp_dir = tempfile.mkdtemp()
    try:
        cache = ToolCache(cache_dir=tmp_dir, default_ttl_seconds=10)
        args = {"ticker": "AAPL", "period": "annual"}
        cache.set("test_tool", args, {"revenue": 391000000000})

        cached_val = cache.get("test_tool", args)
        assert cached_val is not None
        assert cached_val["revenue"] == 391000000000

        miss_val = cache.get("test_tool", {"ticker": "MSFT"})
        assert miss_val is None
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

def test_rate_limiter_acquire():
    """Verify APIRateLimiter token bucket allows timely acquisition."""
    from tools.rate_limiter import APIRateLimiter

    limiter = APIRateLimiter()
    limiter.acquire("sec_filing_search", rps=10.0)
    limiter.acquire("financial_data_api", rps=5.0)

def test_news_sentiment_tool_scoring():
    """Verify NewsSentimentTool calculates polarity and subjectivity."""
    from tools.news_sentiment import NewsSentimentTool

    tool = NewsSentimentTool()
    res = tool.run(query="Apple record services revenue and iPhone demand", num_articles=2)

    assert "overall_sentiment" in res
    assert "average_polarity" in res
    assert "average_subjectivity" in res
    assert len(res["articles"]) > 0
    assert res["overall_sentiment"] in ["BULLISH", "BEARISH", "NEUTRAL"]

def test_financial_data_api_fallback_and_structure():
    """Verify FinancialDataApiTool returns standardized financial statement data."""
    from tools.financial_api import FinancialDataApiTool

    tool = FinancialDataApiTool()
    res = tool._generate_fallback_data(ticker="MSFT", statement_type="income_statement")

    assert res["ticker"] == "MSFT"
    assert "market_cap" in res
    assert "operating_margins" in res
    assert "financial_statements" in res

def test_earnings_transcript_tool():
    """Verify EarningsTranscriptTool retrieves structured conference call Q&A."""
    from tools.earnings import EarningsTranscriptTool

    tool = EarningsTranscriptTool()
    res = tool.run(ticker="TSLA", quarter="Q3", year=2024)

    assert res["ticker"] == "TSLA"
    assert len(res["participants"]["executives"]) >= 2
    assert any("Elon Musk" in e["name"] for e in res["participants"]["executives"])
    assert len(res["prepared_remarks"]) >= 2
    assert len(res["qa_session"]) >= 2
    assert "guidance_summary" in res
    assert res["source_tier"] == 3

def test_company_profile_tool():
    """Verify CompanyProfileTool retrieves corporate metadata and CIK."""
    from tools.company_profile import CompanyProfileTool

    tool = CompanyProfileTool()
    res = tool.run(ticker="TSLA")

    assert res["ticker"] == "TSLA"
    assert res["company_name"] == "Tesla, Inc."
    assert res["sector"] == "Consumer Cyclical"
    assert "Musk" in res["ceo"]
    assert "Automotive" in res["description"]
    assert len(res["business_segments"]) >= 2

def test_peer_comparison_tool():
    """Verify PeerComparisonTool builds cloud competitor comparison matrix."""
    from tools.peer_comparison import PeerComparisonTool

    tool = PeerComparisonTool()
    res = tool.run(ticker="AMZN", num_peers=3)

    assert res["target_ticker"] == "AMZN"
    assert len(res["peer_comparison_matrix"]) >= 3
    tickers = [p["ticker"] for p in res["peer_comparison_matrix"]]
    assert "AMZN" in tickers
    assert "MSFT" in tickers
    assert "GOOGL" in tickers
    assert "sector_insights" in res

def test_calculation_engine_tool():
    """Verify CalculationEngineTool computes DCF, WACC, CAGR, and margins."""
    from tools.calculator import CalculationEngineTool

    calc = CalculationEngineTool()

    dcf_res = calc.run(
        calculation_type="dcf",
        inputs={
            "free_cash_flows": [100.0, 115.0, 130.0, 145.0, 160.0],
            "discount_rate": 0.09,
            "terminal_growth_rate": 0.025,
            "shares_outstanding": 10.0,
            "net_debt": 50.0,
        }
    )
    assert dcf_res["model"] == "Discounted Cash Flow (DCF)"
    assert dcf_res["enterprise_value"] > 0
    assert dcf_res["implied_share_price"] > 0

    wacc_res = calc.run(
        calculation_type="wacc",
        inputs={"equity_value": 800.0, "debt_value": 200.0, "cost_of_equity": 0.10, "cost_of_debt": 0.05, "tax_rate": 0.21}
    )
    assert "wacc_percentage" in wacc_res
    assert wacc_res["wacc_decimal"] > 0.07

    cagr_res = calc.run(calculation_type="cagr", inputs={"start_val": 100.0, "end_val": 200.0, "periods": 3})
    assert cagr_res["cagr_decimal"] > 0.25

    margin_res = calc.run(calculation_type="margin", inputs={"numerator": 45.0, "revenue": 100.0})
    assert margin_res["margin_percentage"] == "45.00%"

def test_fact_checker_tool():
    """Verify FactCheckerTool cross-references claims against authoritative data."""
    from tools.fact_checker import FactCheckerTool

    fc = FactCheckerTool()
    res = fc.run(claim="Microsoft reported FY24 total revenue of $245.12 Billion with 44.6% operating margin.")

    assert res["status"] == "VERIFIED"
    assert res["confidence_score"] >= 0.90
    assert len(res["verified_findings"]) >= 1
    assert any("245.12" in f for f in res["verified_findings"])

def test_report_generator_tool():
    """Verify ReportGeneratorTool formats sections into institutional Markdown."""
    from tools.report_gen import ReportGeneratorTool

    rg = ReportGeneratorTool()
    sections = {
        "title": "Tesla Risk Assessment Report",
        "executive_summary": "Comprehensive institutional risk assessment for Tesla, Inc.",
        "financial_risks": [
            "Gross margin compression driven by global EV price discounting.",
            "Capital expenditure intensity related to AI datacenter compute.",
        ],
        "regulatory_risks": "NHTSA investigations into Full Self-Driving (FSD) Autopilot incidents.",
    }
    sources = ["SEC Form 10-K", "Tesla Q3 Earnings Transcript", "Reuters Automotive News"]

    res = rg.run(template="risk_assessment", sections=sections, sources=sources)

    assert "report_markdown" in res
    assert "# Tesla Risk Assessment Report" in res["report_markdown"]
    assert "## Financial Risks" in res["report_markdown"]
    assert "## Regulatory Risks" in res["report_markdown"]
    assert "NHTSA investigations" in res["report_markdown"]
    assert res["sources_count"] == 3

