"""Human Analyst Benchmarks for ARA-1 Evaluation.

Houses ground-truth benchmark datasets representing senior equity research
standards (e.g. Goldman Sachs, Morgan Stanley, JPMorgan) for:
- Microsoft Corporation (NASDAQ: MSFT)
- Apple Inc. (NASDAQ: AAPL)
- Tesla, Inc. (NASDAQ: TSLA)
"""

from typing import Dict, Any, Optional

MSFT_BENCHMARK: Dict[str, Any] = {
    "ticker": "MSFT",
    "company_name": "Microsoft Corporation",
    "primary_exchange": "NASDAQ",
    "benchmark_source": "Goldman Sachs Global Investment Research / SEC Form 10-K",
    "fiscal_year": 2024,
    "key_executives": {
        "ceo": "Satya Nadella",
        "cfo": "Amy Hood",
    },
    "ground_truth_metrics": {
        "revenue": 245.12,
        "revenue_growth_yoy": 15.7,
        "gross_margin": 69.8,
        "operating_income": 109.43,
        "operating_margin": 44.6,
        "net_income": 88.14,
        "diluted_eps": 11.80,
        "free_cash_flow": 74.07,
        "intelligent_cloud_revenue": 105.36,
        "intelligent_cloud_growth": 19.0,
        "azure_growth": 29.0,
        "productivity_revenue": 77.71,
        "productivity_growth": 12.0,
        "more_personal_computing_revenue": 62.05,
        "more_personal_computing_growth": 13.0,
    },
    "required_sections": [
        "Executive Summary",
        "Business Overview",
        "Segment Breakdown",
        "Financial Summary",
        "Leadership",
        "Governance",
        "Strategic Catalysts",
        "Risks",
        "Methodology",
    ],
    "key_risk_factors": [
        "regulatory scrutiny",
        "gpu supply chain",
        "cloud competition",
        "capex intensity",
        "ai monetization",
    ],
    "authoritative_sources": [
        "SEC Form 10-K",
        "financial_data_api",
        "company_profile",
        "web_search",
    ],
}

AAPL_BENCHMARK: Dict[str, Any] = {
    "ticker": "AAPL",
    "company_name": "Apple Inc.",
    "primary_exchange": "NASDAQ",
    "benchmark_source": "Morgan Stanley Equity Research / SEC Form 10-K / Q4 Transcripts",
    "fiscal_period": "Q4 FY24",
    "key_executives": {
        "ceo": "Tim Cook",
        "cfo": "Luca Maestri",
    },
    "ground_truth_metrics": {
        "reported_revenue": 94.93,
        "consensus_revenue": 94.58,
        "revenue_beat": 0.35,
        "revenue_growth_yoy": 6.1,
        "products_revenue": 69.96,
        "services_revenue": 24.97,
        "services_growth_yoy": 11.9,
        "gross_margin": 46.2,
        "services_gross_margin": 74.0,
        "products_gross_margin": 36.3,
        "operating_income": 29.59,
        "reported_eps": 1.64,
        "consensus_eps": 1.60,
        "eps_beat": 0.04,
        "active_devices": 2.2,
        "operating_cash_flow": 26.8,
        "guidance_gross_margin_low": 46.0,
        "guidance_gross_margin_high": 47.0,
    },
    "required_sections": [
        "Executive Summary",
        "Consensus Expectations",
        "Segment Breakdown",
        "Profitability",
        "Cash Flow",
        "Forward Guidance",
        "Sentiment",
        "Risks",
    ],
    "key_risk_factors": [
        "digital markets act",
        "antitrust litigation",
        "china competition",
        "hardware replacement cycle",
    ],
    "authoritative_sources": [
        "SEC Form 10-K",
        "Form 10-Q",
        "financial_data_api",
        "earnings_transcript",
        "news_sentiment",
    ],
}

TSLA_BENCHMARK: Dict[str, Any] = {
    "ticker": "TSLA",
    "company_name": "Tesla, Inc.",
    "primary_exchange": "NASDAQ",
    "benchmark_source": "Bernstein Institutional Equity Research / SEC Form 10-K Item 1A",
    "fiscal_year": 2024,
    "key_executives": {
        "ceo": "Elon Musk",
    },
    "ground_truth_metrics": {
        "market_cap": 820.50,
        "enterprise_value": 795.20,
        "cash_and_equivalents": 29.1,
        "auto_gross_margin_ex_credits": 16.4,
        "peak_auto_margin_2022": 29.3,
        "operating_margin": 7.8,
        "regulatory_credits": 2.05,
        "credits_pct_of_net_income": 28.0,
        "capex": 11.2,
    },
    "required_sections": [
        "Executive Summary",
        "Risk Matrix",
        "Financial & Margin Risks",
        "Manufacturing",
        "Regulatory",
        "Autopilot / FSD",
        "Geopolitical",
        "China Exposure",
        "Competitive Pressure",
    ],
    "key_risk_factors": [
        "automotive gross margin contraction",
        "regulatory credit dependency",
        "4680 cell yield and cathode dry-coating",
        "cybertruck ramp",
        "nhtsa autopilot investigations",
        "shanghai gigafactory concentration",
        "chinese ev price war",
        "robotaxi execution",
    ],
    "authoritative_sources": [
        "SEC Form 10-K Item 1A",
        "Form 10-Q",
        "calculation_engine",
        "financial_data_api",
    ],
}

NVDA_BENCHMARK: Dict[str, Any] = {
    "ticker": "NVDA",
    "company_name": "NVIDIA Corporation",
    "primary_exchange": "NASDAQ",
    "benchmark_source": "Goldman Sachs / Morgan Stanley Semiconductor Research / SEC Form 10-K",
    "fiscal_year": 2024,
    "key_executives": {
        "ceo": "Jensen Huang",
        "cfo": "Colette Kress",
    },
    "ground_truth_metrics": {
        "revenue": 60.92,
        "revenue_growth_yoy": 125.9,
        "data_center_revenue": 47.53,
        "gross_margin": 72.7,
        "operating_income": 32.97,
        "operating_margin": 54.1,
        "diluted_eps": 1.19,
        "free_cash_flow": 27.02,
        "target_price": 165.00,
    },
    "required_sections": [
        "Executive Summary",
        "Silicon Architecture",
        "Financial Analysis",
        "Data Center",
        "Competitive Moat",
        "Supply Chain",
        "Valuation Modeling",
        "Risk Assessment",
        "Scenario Analysis",
        "Data Provenance",
    ],
    "key_risk_factors": [
        "customer concentration",
        "hyperscaler custom silicon",
        "taiwan foundry concentration",
        "china export regulations",
        "datacenter power constraints",
    ],
    "authoritative_sources": [
        "SEC Form 10-K",
        "Form 10-Q",
        "ChromaDB",
        "calculation_engine",
        "peer_comparison",
    ],
}

BENCHMARKS: Dict[str, Dict[str, Any]] = {
    "MSFT": MSFT_BENCHMARK,
    "AAPL": AAPL_BENCHMARK,
    "TSLA": TSLA_BENCHMARK,
    "NVDA": NVDA_BENCHMARK,
}

def get_benchmark(ticker: str) -> Optional[Dict[str, Any]]:
    """Retrieve human analyst benchmark for a specific ticker."""
    return BENCHMARKS.get(ticker.upper())

def load_all_benchmarks() -> Dict[str, Dict[str, Any]]:
    """Retrieve all loaded human analyst benchmarks."""
    return BENCHMARKS
