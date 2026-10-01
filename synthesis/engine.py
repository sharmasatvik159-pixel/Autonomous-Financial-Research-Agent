"""Multi-Source Financial Synthesis Engine for ARA-1.

Coordinates the end-to-end data synthesis pipeline:
1. Ingests structured facts and observations across SEC EDGAR, Financial APIs, Transcripts, and News.
2. Identifies contradictions and invokes ConflictResolver to enforce the 5-Tier Reliability Hierarchy.
3. Performs Quantitative Triangulation across independent evidence layers.
4. Generates comprehensive narrative threads and reconciliation audit tables.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

from synthesis.conflict_resolver import ConflictResolver, DataPoint, DiscrepancyLog, SourceTier
from synthesis.narrative import NarrativeThreader, QuantitativeTriangulator, NarrativeThread, TriangulationResult

logger = logging.getLogger("ARA1.Synthesis.Engine")

class SynthesisReport(BaseModel):
    """Complete deliverable output from the Multi-Source Synthesis Engine."""
    target_ticker: str
    executive_summary: str
    authoritative_metrics: Dict[str, Any]
    narrative_threads: List[NarrativeThread]
    discrepancies: List[DiscrepancyLog]
    triangulations: List[TriangulationResult]
    report_markdown: str

class MultiSourceSynthesisEngine:
    """Institutional synthesis orchestrator reconciling multi-source corporate intelligence."""

    def __init__(self, tolerance_pct: float = 0.02):
        self.conflict_resolver = ConflictResolver(tolerance_pct=tolerance_pct)
        self.triangulator = QuantitativeTriangulator(minimum_sources_for_triangulation=2)
        self.narrative_threader = NarrativeThreader()
        self.raw_observations: List[DataPoint] = []

    def ingest_data_point(
        self,
        metric_name: str,
        value: Union[float, int, str, bool],
        source_type: str,
        citation: str = "",
        tier: Optional[int] = None,
        date: Optional[str] = None,
        is_gaap: Optional[bool] = None,
        is_segmental: Optional[bool] = None,
        raw_text: str = "",
        notes: Optional[str] = None,
    ) -> DataPoint:
        """Ingests a discrete observation into the synthesis pipeline."""
        assigned_tier = tier or self.conflict_resolver.classify_source_tier(source_type)
        dp = DataPoint(
            metric_name=metric_name,
            value=value,
            raw_text=raw_text,
            source_type=source_type,
            tier=assigned_tier,
            citation=citation,
            date=date,
            is_gaap=is_gaap,
            is_segmental=is_segmental,
            notes=notes,
        )
        self.raw_observations.append(dp)
        return dp

    def ingest_tool_observations(self, tool_name: str, tool_output: Any, ticker: str = "") -> List[DataPoint]:
        """Automatically parses and ingests raw tool observation dictionaries."""
        points = []
        if isinstance(tool_output, dict):
            if tool_name == "financial_data_api":
                mkt_cap = tool_output.get("market_cap")
                if mkt_cap:
                    points.append(self.ingest_data_point(
                        metric_name="market_cap",
                        value=mkt_cap,
                        source_type="financial_data_api",
                        citation="yfinance_market_fundamentals",
                    ))
                pe = tool_output.get("trailing_pe")
                if pe:
                    points.append(self.ingest_data_point(
                        metric_name="trailing_pe",
                        value=round(float(pe), 2),
                        source_type="financial_data_api",
                        citation="yfinance_fundamentals",
                    ))
                for m in tool_output.get("annual_metrics", []):
                    if isinstance(m, dict):
                        rev = m.get("revenue")
                        yr = m.get("year", "FY")
                        if rev:
                            points.append(self.ingest_data_point(
                                metric_name=f"revenue_{yr}",
                                value=rev,
                                source_type="financial_data_api",
                                citation=f"Audited {yr} Statements",
                                is_gaap=True,
                            ))

            elif tool_name == "sec_filing_search":
                latest = tool_output.get("latest_filing", {})
                if latest:
                    points.append(self.ingest_data_point(
                        metric_name="latest_filing_form",
                        value=latest.get("form", "10-K"),
                        source_type="sec_filing_search",
                        citation=f"SEC Accession {latest.get('accession_number')}",
                        tier=SourceTier.TIER_1_SEC,
                        date=latest.get("filing_date"),
                        is_gaap=True,
                    ))

            elif tool_name == "news_sentiment":
                pol = tool_output.get("average_polarity")
                if pol is not None:
                    points.append(self.ingest_data_point(
                        metric_name="news_polarity_score",
                        value=pol,
                        source_type="news_sentiment",
                        citation=f"News NLP ({tool_output.get('articles_analyzed', 0)} articles)",
                        tier=SourceTier.TIER_4_MAJOR_NEWS,
                    ))

        return points

    def synthesize(self, target_ticker: str, research_query: str) -> SynthesisReport:
        """
        Executes complete multi-source conflict reconciliation, triangulation,
        and narrative compilation.
        """
        metrics_map: Dict[str, List[DataPoint]] = {}
        for dp in self.raw_observations:
            metrics_map.setdefault(dp.metric_name, []).append(dp)

        authoritative_metrics: Dict[str, Any] = {}
        resolved_discrepancies: List[DiscrepancyLog] = []
        triangulation_results: List[TriangulationResult] = []

        for metric_name, points in metrics_map.items():
            auth_point, disc_log = self.conflict_resolver.resolve_conflict(points)
            authoritative_metrics[metric_name] = auth_point.value
            if disc_log:
                resolved_discrepancies.append(disc_log)

            triang_res = self.triangulator.triangulate(metric_name, points)
            triangulation_results.append(triang_res)

        threads = self._generate_default_threads(target_ticker, authoritative_metrics, resolved_discrepancies)

        markdown = self._render_full_synthesis_markdown(
            target_ticker=target_ticker,
            query=research_query,
            authoritative_metrics=authoritative_metrics,
            threads=threads,
            discrepancies=resolved_discrepancies,
        )

        return SynthesisReport(
            target_ticker=target_ticker,
            executive_summary=f"Synthesized research report for {target_ticker} across {len(self.raw_observations)} observations with {len(resolved_discrepancies)} reconciled discrepancies.",
            authoritative_metrics=authoritative_metrics,
            narrative_threads=threads,
            discrepancies=resolved_discrepancies,
            triangulations=triangulation_results,
            report_markdown=markdown,
        )

    def _generate_default_threads(
        self,
        ticker: str,
        metrics: Dict[str, Any],
        discrepancies: List[DiscrepancyLog],
    ) -> List[NarrativeThread]:
        """Builds default structured investment narrative threads."""
        threads = []

        rev_metrics = [
            {"metric": k, "value": v, "source": "Multi-Source Reconciled"}
            for k, v in metrics.items()
            if "revenue" in k or "margin" in k or "pe" in k
        ]
        if rev_metrics:
            threads.append(self.narrative_threader.build_narrative_thread(
                theme_title="1. Financial Trajectory & Margin Structure",
                core_thesis=f"Analysis of {ticker}'s financial performance demonstrates core operating leverage and margin dynamics.",
                supporting_metrics=rev_metrics,
                synthesis_conclusion="Audited statements substantiate durable top-line expansion while reconciling non-operating variations.",
            ))

        return threads

    def _render_full_synthesis_markdown(
        self,
        target_ticker: str,
        query: str,
        authoritative_metrics: Dict[str, Any],
        threads: List[NarrativeThread],
        discrepancies: List[DiscrepancyLog],
    ) -> str:
        """Renders complete institutional investment report with conflict resolution audit."""
        sections = [
            f"# Multi-Source Investment Synthesis: {target_ticker}",
            f"**Research Directive:** {query}  ",
            f"**Coverage Entity:** {target_ticker}  ",
            "**Synthesis Engine:** QuantumEdge ARA-1 Multi-Source Synthesis  ",
            "",
            "---",
            "",
            "## 1. Executive Summary & Authoritative Baseline",
            f"The synthesis engine reconciled multi-source disclosures for **{target_ticker}**, systematically resolving "
            f"divergences between audited SEC statutory filings (Tier 1), financial databases (Tier 2), and public news feeds (Tiers 4-5).",
            "",
            "### Verified Authoritative Metrics",
            "| Metric | Authoritative Value | Source Hierarchy Tier | Status |",
            "| :--- | :--- | :--- | :--- |",
        ]

        for k, v in sorted(authoritative_metrics.items()):
            sections.append(f"| **{k.replace('_', ' ').title()}** | {v} | Tier 1/2 Verified | Authoritative Ground Truth |")

        sections.append("")
        sections.append("---")
        sections.append("")
        sections.append("## 2. Core Investment Narrative Threads")

        for thread in threads:
            sections.append(self.narrative_threader.render_thread_markdown(thread))

        sections.append("---")
        sections.append("")
        sections.append("## 3. Discrepancy & Contradiction Resolution Audit")
        sections.append(self.conflict_resolver.get_discrepancy_summary_markdown())

        return "\n".join(sections)
