"""Tool Schemas package for ARA-1.

Contains Pydantic schema models and JSON function-calling definitions
for all 10+ financial research tools.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class SecFilingSearchInput(BaseModel):
    ticker: str = Field(description="Stock ticker symbol (e.g. AAPL, MSFT, TSLA)")
    filing_type: str = Field(
        description="Type of SEC filing to retrieve ('10-K', '10-Q', '8-K', 'DEF 14A')"
    )
    year: Optional[int] = Field(default=None, description="Filing year (defaults to most recent)")

class WebSearchInput(BaseModel):
    query: str = Field(description="Search query string for financial news, events, or commentary")
    num_results: int = Field(default=10, description="Maximum number of search results to return")
    date_range: Optional[str] = Field(default=None, description="Date filter (e.g. 'past_week', 'past_year')")

class EarningsTranscriptInput(BaseModel):
    ticker: str = Field(description="Company ticker symbol")
    quarter: str = Field(description="Quarter ('Q1', 'Q2', 'Q3', 'Q4')")
    year: int = Field(description="Fiscal year of the earnings call")

class FinancialDataApiInput(BaseModel):
    ticker: str = Field(description="Company ticker symbol")
    statement_type: str = Field(
        description="Statement type: 'income_statement', 'balance_sheet', 'cash_flow', or 'ratios'"
    )
    period: str = Field(default="annual", description="Period type: 'annual' or 'quarterly'")
    years: int = Field(default=3, description="Number of years/periods of historical data")

class NewsSentimentInput(BaseModel):
    query: str = Field(description="Company name, ticker, or topic to analyze sentiment for")
    num_articles: int = Field(default=10, description="Number of news articles to score")
    lookback_days: int = Field(default=30, description="Lookback window in days")

class VectorDbSearchInput(BaseModel):
    query: str = Field(description="Semantic search query across long-term research memory")
    top_k: int = Field(default=5, description="Number of top relevant chunks to retrieve")
    limit: Optional[int] = Field(default=None, description="Optional alias for top_k")
    filter: Optional[Dict[str, Any]] = Field(default=None, description="Metadata filter (ticker, source_type, etc.)")

class VectorDbStoreInput(BaseModel):
    content: str = Field(description="Research finding or text chunk to persist into long-term memory")
    metadata: Dict[str, Any] = Field(
        description="Metadata dictionary with ticker, date, source_type, confidence, etc."
    )

class CompanyProfileInput(BaseModel):
    ticker: str = Field(description="Stock ticker symbol")

class PeerComparisonInput(BaseModel):
    ticker: str = Field(description="Target company ticker symbol")
    num_peers: int = Field(default=4, description="Number of industry peer companies to analyze")
    metrics: List[str] = Field(
        default_factory=lambda: ["revenue_growth", "operating_margin", "pe_ratio", "ev_to_ebitda"],
        description="List of financial metrics to compare"
    )

class CalculationEngineInput(BaseModel):
    calculation_type: str = Field(
        description="Type of calculation ('dcf', 'pe_ratio', 'cagr', 'wacc', 'margin', 'growth')"
    )
    inputs: Dict[str, Any] = Field(description="Numerical parameters required for the selected calculation")

class FactCheckerInput(BaseModel):
    claim: str = Field(description="Specific numerical or factual statement to verify")
    sources: Optional[List[str]] = Field(default=None, description="Optional list of source documents or URLs to test against")

class ReportGeneratorInput(BaseModel):
    template: str = Field(
        default="standard_research_report",
        description="Report template format ('standard_research_report', 'earnings_analysis', 'risk_assessment')"
    )
    sections: Dict[str, Any] = Field(description="Content dictionary mapping section titles to synthesized text/tables")
    sources: List[str] = Field(default_factory=list, description="List of authoritative cited sources")

__all__ = [
    "SecFilingSearchInput",
    "WebSearchInput",
    "EarningsTranscriptInput",
    "FinancialDataApiInput",
    "NewsSentimentInput",
    "VectorDbSearchInput",
    "VectorDbStoreInput",
    "CompanyProfileInput",
    "PeerComparisonInput",
    "CalculationEngineInput",
    "FactCheckerInput",
    "ReportGeneratorInput",
]
