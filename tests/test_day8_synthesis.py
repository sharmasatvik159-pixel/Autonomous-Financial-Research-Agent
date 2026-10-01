"""Day 8 Multi-Source Synthesis & Conflict Resolution Test Suite.

Tests synthesis components under synthesis/:
- synthesis/conflict_resolver.py: 5-Tier reliability hierarchy, contradiction detection, and discrepancy logging
- synthesis/narrative.py: Quantitative triangulation across independent sources and narrative threading
- synthesis/engine.py: MultiSourceSynthesisEngine pipeline reconciling conflicting corporate disclosures
"""

import pytest
from synthesis.conflict_resolver import (
    ConflictResolver,
    DataPoint,
    SourceTier,
    DiscrepancyLog,
)
from synthesis.narrative import (
    QuantitativeTriangulator,
    NarrativeThreader,
    NarrativeThread,
    TriangulationResult,
)
from synthesis.engine import (
    MultiSourceSynthesisEngine,
    SynthesisReport,
)

def test_source_hierarchy_precedence():
    """Verify that Tier 1 (SEC 10-K) takes precedence over Tier 4 (News) and Tier 5 (Web rumors)."""
    resolver = ConflictResolver()

    dp_sec = DataPoint(
        metric_name="fy24_revenue",
        value=2866.0,
        source_type="sec_10k",
        tier=SourceTier.TIER_1_SEC,
        citation="SEC Form 10-K Item 8",
        is_gaap=True,
    )
    dp_news = DataPoint(
        metric_name="fy24_revenue",
        value=3100.0,
        source_type="reuters_wire",
        tier=SourceTier.TIER_4_MAJOR_NEWS,
        citation="Reuters Press Article",
    )
    dp_web = DataPoint(
        metric_name="fy24_revenue",
        value=3500.0,
        source_type="social_forum",
        tier=SourceTier.TIER_5_UNVERIFIED_WEB,
        citation="Reddit StockTwits Rumor",
    )

    winner, disc = resolver.resolve_conflict([dp_web, dp_news, dp_sec])
    assert winner.tier == SourceTier.TIER_1_SEC
    assert winner.value == 2866.0
    assert winner.source_type == "sec_10k"
    assert disc is not None
    assert disc.winning_tier == SourceTier.TIER_1_SEC
    assert disc.winning_source == "sec_10k"
    assert disc.authoritative_value == 2866.0
    assert disc.variance_percentage is not None

def test_gaap_vs_non_gaap_conflict_resolution():
    """Verify detection and diagnostic categorization of GAAP vs Non-GAAP operating margin differences."""
    resolver = ConflictResolver()

    dp_gaap = DataPoint(
        metric_name="operating_income",
        value=342.0,
        source_type="sec_10k",
        tier=SourceTier.TIER_1_SEC,
        citation="SEC 10-K Audited Consolidated Financials",
        is_gaap=True,
    )
    dp_nongaap = DataPoint(
        metric_name="operating_income",
        value=980.0,
        source_type="earnings_transcript",
        tier=SourceTier.TIER_3_EARNINGS_TRANSCRIPT,
        citation="Q4 Earnings Conference Call Remarks",
        is_gaap=False,
    )

    winner, disc = resolver.resolve_conflict([dp_gaap, dp_nongaap])
    assert winner.value == 342.0
    assert disc is not None
    assert disc.resolution_status == "GAAP_VS_NON_GAAP"
    assert "stock-based compensation" in disc.explanation.lower() or "gaap" in disc.explanation.lower()

def test_segmental_vs_consolidated_conflict():
    """Verify diagnostic categorization when divisional growth is conflated with consolidated growth."""
    resolver = ConflictResolver()

    dp_consolidated = DataPoint(
        metric_name="revenue_growth_yoy",
        value=24.0,
        source_type="sec_10k",
        tier=SourceTier.TIER_1_SEC,
        is_segmental=False,
    )
    dp_segment = DataPoint(
        metric_name="revenue_growth_yoy",
        value=54.0,
        source_type="press_release",
        tier=SourceTier.TIER_4_MAJOR_NEWS,
        is_segmental=True,
    )

    winner, disc = resolver.resolve_conflict([dp_consolidated, dp_segment])
    assert winner.value == 24.0
    assert disc is not None
    assert disc.resolution_status == "SEGMENTAL_VS_CONSOLIDATED"

def test_quantitative_triangulation():
    """Verify triangulation across >= 2 independent concordant sources."""
    triangulator = QuantitativeTriangulator(minimum_sources_for_triangulation=2)

    dp1 = DataPoint(
        metric_name="customer_count",
        value=496,
        source_type="sec_10k",
        tier=SourceTier.TIER_1_SEC,
    )
    dp2 = DataPoint(
        metric_name="customer_count",
        value=496,
        source_type="financial_data_api",
        tier=SourceTier.TIER_2_FINANCIAL_API,
    )

    res = triangulator.triangulate("Palantir Total Commercial & Government Customers", [dp1, dp2])
    assert res.verified is True
    assert res.verdict == "TRIANGULATED_CONFIRMED"
    assert res.source_count == 2
    assert res.confidence_score >= 0.85

    dp_conflict = DataPoint(
        metric_name="customer_count",
        value=850,
        source_type="web_blog",
        tier=SourceTier.TIER_5_UNVERIFIED_WEB,
    )
    res_conflict = triangulator.triangulate("Palantir Customer Count Claim", [dp1, dp_conflict])
    assert res_conflict.verified is False
    assert res_conflict.verdict == "CONTRADICTED"

def test_narrative_threading():
    """Verify narrative thread construction and markdown rendering."""
    threader = NarrativeThreader()
    thread = threader.build_narrative_thread(
        theme_title="US Commercial Momentum vs Government Stability",
        core_thesis="Palantir exhibits a bifurcation between mature US government contracts and accelerating private sector adoption.",
        supporting_metrics=[
            {"metric": "US Commercial Revenue", "value": "$550M (+54% YoY)", "source": "SEC 10-K"},
            {"metric": "Government Revenue", "value": "$1.2B (+14% YoY)", "source": "SEC 10-K"},
        ],
        management_perspective="AIP is driving unprecedented commercial deal conversions across US enterprises.",
        regulatory_or_risk_factor="Concentration in multi-year defense budget approval cycles.",
        synthesis_conclusion="Commercial expansion reduces defense spending cyclicality and provides operational margin leverage.",
    )

    md = threader.render_thread_markdown(thread)
    assert "### US Commercial Momentum" in md
    assert "$550M" in md
    assert "Executive Commentary" in md
    assert "AIP is driving unprecedented" in md

def test_multisource_synthesis_engine_end_to_end():
    """Verify end-to-end synthesis engine pipeline for Palantir Technologies (PLTR)."""
    engine = MultiSourceSynthesisEngine()

    engine.ingest_data_point(
        metric_name="fy24_revenue",
        value="$2.866 Billion",
        source_type="sec_10k",
        tier=SourceTier.TIER_1_SEC,
        citation="SEC Form 10-K Audited Consolidated Results",
        is_gaap=True,
    )
    engine.ingest_data_point(
        metric_name="fy24_revenue",
        value="$3.100 Billion",
        source_type="reuters_wire",
        tier=SourceTier.TIER_4_MAJOR_NEWS,
        citation="Reuters Technology Desk",
    )

    engine.ingest_data_point(
        metric_name="operating_margin",
        value="11.9% (GAAP)",
        source_type="sec_10k",
        tier=SourceTier.TIER_1_SEC,
        citation="SEC Form 10-K MD&A",
        is_gaap=True,
    )
    engine.ingest_data_point(
        metric_name="operating_margin",
        value="34.0% (Adjusted)",
        source_type="earnings_call",
        tier=SourceTier.TIER_3_EARNINGS_TRANSCRIPT,
        citation="Q4 Conference Call Non-GAAP Metric",
        is_gaap=False,
    )

    engine.ingest_data_point(
        metric_name="market_cap",
        value="$95.4 Billion",
        source_type="financial_data_api",
        tier=SourceTier.TIER_2_FINANCIAL_API,
        citation="yfinance fundamentals",
    )

    report = engine.synthesize(
        target_ticker="PLTR",
        research_query="Reconcile contradictory financial disclosures, GAAP margins, and commercial growth claims for Palantir Technologies.",
    )

    assert isinstance(report, SynthesisReport)
    assert report.target_ticker == "PLTR"
    assert len(report.discrepancies) >= 1
    assert "Discrepancy & Contradiction Resolution Audit" in report.report_markdown
    assert "Authoritative Ground Truth" in report.report_markdown
    assert "$2.866 Billion" in report.report_markdown
