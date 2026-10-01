"""Source Reliability Hierarchy & Conflict Resolution Engine for ARA-1.

Implements the corrected 5-Tier Source Reliability Hierarchy:
- Tier 1: SEC Statutory Filings (Form 10-K, 10-Q, 8-K) — Audited, legal liability (Confidence: 1.0)
- Tier 2: Institutional Financial APIs (yfinance, FMP, Morningstar) — Structured fundamentals (Confidence: 0.85)
- Tier 3: Corporate Disclosures & Earnings Transcripts — Direct executive commentary (Confidence: 0.70)
- Tier 4: Major Financial News Outlets (Reuters, Bloomberg, FT, WSJ) — Editorial review (Confidence: 0.50)
- Tier 5: Crowdsourced / Web Feeds (Social media, anonymous forums, speculative blogs) — Unverified (Confidence: 0.25)

Resolves discrepancies between competing data points, logs contradictions, and establishes
authoritative ground truth with audit provenance.
"""

from __future__ import annotations
import logging
import math
import re
from typing import Dict, Any, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

logger = logging.getLogger("ARA1.Synthesis.ConflictResolver")


class SourceTier:
    """Standardized source hierarchy definitions and priority order."""
    TIER_1_SEC = 1
    TIER_2_FINANCIAL_API = 2
    TIER_3_EARNINGS_TRANSCRIPT = 3
    TIER_4_MAJOR_NEWS = 4
    TIER_5_UNVERIFIED_WEB = 5

    TIER_CONFIDENCE: Dict[int, float] = {
        1: 1.00,
        2: 0.85,
        3: 0.70,
        4: 0.50,
        5: 0.25,
    }

    TIER_DESCRIPTIONS: Dict[int, str] = {
        1: "Tier 1: SEC Statutory Filings (Audited 10-K, 10-Q, 8-K)",
        2: "Tier 2: Institutional Financial APIs & Market Fundamentals",
        3: "Tier 3: Executive Transcripts & Direct Management Disclosures",
        4: "Tier 4: Premier Financial Journalism (Reuters, Bloomberg, FT)",
        5: "Tier 5: Crowdsourced / Unverified Web Commentary",
    }


class DataPoint(BaseModel):
    """Represents a specific metric observation retrieved from a source."""
    metric_name: str
    value: Union[float, int, str, bool]
    raw_text: str = ""
    source_type: str = Field(description="e.g. '10-K', 'yfinance', 'earnings_transcript', 'news', 'web'")
    tier: int = Field(default=SourceTier.TIER_4_MAJOR_NEWS, ge=1, le=5)
    citation: str = Field(default="", description="Filing accession, article headline, or URL")
    date: Optional[str] = None
    is_gaap: Optional[bool] = None
    is_segmental: Optional[bool] = None
    notes: Optional[str] = None

    @property
    def confidence(self) -> float:
        return SourceTier.TIER_CONFIDENCE.get(self.tier, 0.5)


class DiscrepancyLog(BaseModel):
    """Detailed record of a detected contradiction across data sources."""
    metric_name: str
    claimed_values: List[Dict[str, Any]]
    authoritative_value: Union[float, int, str, bool]
    winning_source: str
    winning_tier: int
    resolution_status: str = Field(
        description="'RESOLVED_BY_HIERARCHY', 'GAAP_VS_NON_GAAP', 'SEGMENTAL_VS_CONSOLIDATED', 'TEMPORAL_LAG'"
    )
    explanation: str
    variance_percentage: Optional[float] = None


class ConflictResolver:
    """Detects, categorizes, and resolves conflicting financial claims."""

    def __init__(self, tolerance_pct: float = 0.02):
        """
        tolerance_pct: Acceptable numerical variance (e.g. 2%) due to rounding before flagging conflict.
        """
        self.tolerance_pct = tolerance_pct
        self.discrepancy_history: List[DiscrepancyLog] = []

    def classify_source_tier(self, source_name_or_type: str) -> int:
        """Classifies any tool or source string into its standardized reliability tier."""
        s = source_name_or_type.lower()
        if any(k in s for k in ("10-k", "10-q", "8-k", "sec", "edgar")):
            return SourceTier.TIER_1_SEC
        elif any(k in s for k in ("yfinance", "fmp", "financial_data_api", "balance_sheet", "income_statement")):
            return SourceTier.TIER_2_FINANCIAL_API
        elif any(k in s for k in ("transcript", "earnings_transcript", "conference_call", "prepared_remarks")):
            return SourceTier.TIER_3_EARNINGS_TRANSCRIPT
        elif any(k in s for k in ("reuters", "bloomberg", "news", "news_sentiment", "ft", "financial times", "wsj")):
            return SourceTier.TIER_4_MAJOR_NEWS
        else:
            return SourceTier.TIER_5_UNVERIFIED_WEB

    def resolve_conflict(self, data_points: List[DataPoint]) -> Tuple[DataPoint, Optional[DiscrepancyLog]]:
        """
        Takes multiple candidate observations for the same metric, evaluates conflicts,
        and returns the authoritative data point alongside a discrepancy log.
        """
        if not data_points:
            raise ValueError("Cannot resolve conflict on empty data_points list.")

        if len(data_points) == 1:
            return data_points[0], None

        metric_name = data_points[0].metric_name

        # Sort primarily by tier (ascending: 1 > 2 > 3 > 4 > 5), secondarily by recency/citation
        sorted_points = sorted(data_points, key=lambda p: (p.tier, 0 if p.is_gaap else 1))
        winner = sorted_points[0]

        # Check if values conflict
        has_conflict = False
        variance_pct: Optional[float] = None
        comp_val = winner.value

        for p in sorted_points[1:]:
            if isinstance(comp_val, (int, float)) and isinstance(p.value, (int, float)):
                if comp_val != 0:
                    diff = abs(float(p.value) - float(comp_val)) / abs(float(comp_val))
                    if diff > self.tolerance_pct:
                        has_conflict = True
                        variance_pct = round(diff * 100, 2)
                        break
                elif p.value != 0:
                    has_conflict = True
                    break
            elif str(comp_val).strip().lower() != str(p.value).strip().lower():
                has_conflict = True
                break

        if not has_conflict:
            # Values are congruent within tolerance
            return winner, None

        # Analyze root cause of conflict
        resolution_status, explanation = self._diagnose_conflict_cause(winner, sorted_points[1:], variance_pct)

        discrepancy = DiscrepancyLog(
            metric_name=metric_name,
            claimed_values=[
                {
                    "source": p.source_type,
                    "tier": p.tier,
                    "tier_name": SourceTier.TIER_DESCRIPTIONS.get(p.tier, "Unknown"),
                    "value": p.value,
                    "citation": p.citation,
                    "is_gaap": p.is_gaap,
                }
                for p in data_points
            ],
            authoritative_value=winner.value,
            winning_source=winner.source_type,
            winning_tier=winner.tier,
            resolution_status=resolution_status,
            explanation=explanation,
            variance_percentage=variance_pct,
        )

        self.discrepancy_history.append(discrepancy)
        logger.warning(
            f"Resolved conflict on '{metric_name}': Authoritative value '{winner.value}' "
            f"from {winner.source_type} (Tier {winner.tier}) over competing sources. "
            f"Cause: {resolution_status} ({explanation})"
        )

        return winner, discrepancy

    def _diagnose_conflict_cause(
        self,
        winner: DataPoint,
        competing_points: List[DataPoint],
        variance_pct: Optional[float]
    ) -> Tuple[str, str]:
        """Diagnoses why sources diverged (GAAP vs Non-GAAP, Segmental vs Consolidated, Temporal, or Tier Hierarchy)."""
        # 1. GAAP vs Non-GAAP distinction
        has_gaap = any(p.is_gaap is True for p in [winner] + competing_points)
        has_nongaap = any(p.is_gaap is False for p in [winner] + competing_points)
        if has_gaap and has_nongaap:
            return (
                "GAAP_VS_NON_GAAP",
                f"Discrepancy caused by GAAP vs Non-GAAP accounting definitions (e.g. inclusion/exclusion of stock-based compensation). "
                f"Authoritative source {winner.source_type} (Tier {winner.tier}) prioritized."
            )

        # 2. Segmental vs Consolidated reporting
        if any(p.is_segmental for p in competing_points) or winner.is_segmental:
            return (
                "SEGMENTAL_VS_CONSOLIDATED",
                f"Discrepancy originates from conflating divisional or geographical segment growth with consolidated corporate totals."
            )

        # 3. Temporal Reporting Lag
        dates = [p.date for p in [winner] + competing_points if p.date]
        if len(set(dates)) > 1:
            return (
                "TEMPORAL_LAG",
                f"Discrepancy stems from temporal reporting mismatch across distinct quarters or release cycles ({', '.join(set(dates))})."
            )

        # 4. Standard Source Hierarchy Override
        other_tiers = [p.tier for p in competing_points]
        return (
            "RESOLVED_BY_HIERARCHY",
            f"Numerical divergence of {variance_pct}% between Tier {winner.tier} ({winner.source_type}) "
            f"and lower-tier sources (Tiers {other_tiers}). Statutory and verified filings take precedence."
        )

    def get_discrepancy_summary_markdown(self) -> str:
        """Renders an institutional Markdown audit table of all detected discrepancies."""
        if not self.discrepancy_history:
            return "*(No conflicting claims detected. All cross-referenced data points congruent.)*"

        lines = [
            "### Multi-Source Discrepancy & Conflict Resolution Audit",
            "",
            "| Metric | Conflicting Claims (Source & Value) | Authoritative Value | Resolution Cause | Precedence Tier |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]

        for d in self.discrepancy_history:
            claims_str = " <br> ".join(
                f"• {c['source']} (T{c['tier']}): **{c['value']}**"
                for c in d.claimed_values
            )
            auth_str = f"**{d.authoritative_value}** ({d.winning_source})"
            cause_str = d.resolution_status.replace("_", " ").title()
            tier_str = f"Tier {d.winning_tier} Statutory Override"

            lines.append(f"| **{d.metric_name}** | {claims_str} | {auth_str} | {cause_str} | {tier_str} |")

        lines.append("")
        lines.append("> [!IMPORTANT]")
        lines.append(
            "> In accordance with QuantumEdge Research compliance standards, statutory SEC filings "
            "(Tier 1) and audited financial statement APIs (Tier 2) strictly supersede secondary press reports, "
            "management guidance extrapolations, and crowdsourced internet commentary."
        )
        return "\n".join(lines)
