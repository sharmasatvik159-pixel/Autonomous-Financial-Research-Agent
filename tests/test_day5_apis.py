"""Day 5 API Integration & Live Verification Test Suite.

Tests external API wrappers under tools/:
- tools/sec_edgar.py: SEC EDGAR search API with mandatory custom User-Agent headers
- tools/financial_api.py: yfinance / fundamental data API for income, balance, and cash flows
- tools/web_search.py: Live web search with fallback
- tools/news_sentiment.py: Financial NLP sentiment scoring
- Cache and rate-limiting wrappers
"""

import pytest
import os
from tools.sec_edgar import SecFilingSearchTool
from tools.financial_api import FinancialDataApiTool
from tools.web_search import WebSearchTool
from tools.news_sentiment import NewsSentimentTool
from tools.cache import get_tool_cache
from tools.rate_limiter import get_rate_limiter
from config.settings import get_settings

def test_sec_edgar_user_agent_and_retrieval():
    """Verify SEC EDGAR tool adheres to SEC User-Agent requirements and returns structured data."""
    settings = get_settings()
    assert settings.SEC_EDGAR_USER_AGENT is not None
    assert "@" in settings.SEC_EDGAR_USER_AGENT or " " in settings.SEC_EDGAR_USER_AGENT

    tool = SecFilingSearchTool()
    result = tool(ticker="MSFT", filing_type="10-K", year=2024)
    assert result.success is True
    data = result.data
    assert isinstance(data, dict)
    assert data.get("ticker") == "MSFT"
    assert "filings_found" in data
    assert "latest_filing" in data
    latest = data["latest_filing"]
    assert latest.get("form") == "10-K"
    assert "accession_number" in latest

def test_financial_api_statements():
    """Verify financial_data_api retrieves income statements, balance sheets, and cash flows."""
    tool = FinancialDataApiTool()

    inc_res = tool(ticker="AAPL", statement_type="income_statement", period="annual", years=2)
    assert inc_res.success is True
    inc_data = inc_res.data
    assert inc_data.get("ticker") == "AAPL"
    assert "market_cap" in inc_data or "revenue" in inc_data or "trailing_pe" in inc_data

    bs_res = tool(ticker="AAPL", statement_type="balance_sheet", period="annual", years=2)
    assert bs_res.success is True
    assert bs_res.data.get("statement_type") == "balance_sheet"

    cf_res = tool(ticker="AAPL", statement_type="cash_flow", period="annual", years=2)
    assert cf_res.success is True
    assert cf_res.data.get("statement_type") == "cash_flow"

def test_web_search_execution():
    """Verify web search tool executes queries without crashing and returns results."""
    tool = WebSearchTool()
    res = tool(query="Microsoft Azure OpenAI enterprise adoption 2024", num_results=3)
    assert res.success is True
    data = res.data
    assert isinstance(data, (list, dict))
    results_list = data if isinstance(data, list) else data.get("results", [])
    assert len(results_list) > 0
    assert "title" in results_list[0]

def test_news_sentiment_nlp():
    """Verify news sentiment scoring tool runs NLP on financial news."""
    tool = NewsSentimentTool()
    res = tool(query="Apple record quarterly services revenue Tim Cook", num_articles=3, lookback_days=30)
    assert res.success is True
    data = res.data
    assert "average_polarity" in data
    assert "overall_sentiment" in data
    assert data["overall_sentiment"] in ("BULLISH", "BEARISH", "NEUTRAL", "POSITIVE", "NEGATIVE")
    assert isinstance(data["articles"], list)

def test_rate_limiter_and_caching_wrapper():
    """Verify rate limiter acquiring and cache storage across API executions."""
    limiter = get_rate_limiter("test_api", rate_per_second=20.0)
    limiter.acquire()

    cache = get_tool_cache()
    test_key = "test_api_key_day5"
    test_payload = {"status": "ok", "value": 42}
    cache.set(test_key, test_payload, ttl_seconds=60)
    retrieved = cache.get(test_key)
    assert retrieved == test_payload
