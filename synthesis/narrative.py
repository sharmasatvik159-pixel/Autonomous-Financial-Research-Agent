"""Narrative Threading and Quantitative Triangulation Module for ARA-1.

Implements:
1. Quantitative Triangulation: Verifies claims against >= 2 independent authoritative sources,
   calculating source concordance and multi-tier verification confidence.
2. Narrative Threading: Synthesizes fragmented corporate facts, audited metrics, and management
   commentary into coherent institutional investment narratives.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from pydantic import BaseModel, Field

from synthesis.conflict_resolver import DataPoint, SourceTier

logger = logging.getLogger("ARA1.Synthesis.Narrative")


class TriangulationResult(BaseModel):
    """Result of cross-referencing a factual or quantitative claim across independent sources."""
    metric_or_claim: str
    verified: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    source_count: int
    concordant_sources: List[str]
    conflicting_sources: List[str] = Field(default_factory=list)
    verdict: str = Field(description="'TRIANGULATED_CONFIRMED', 'SINGLE_SOURCE_UNCONFIRMED', 'CONTRADICTED'")
    narrative_explanation: str


class NarrativeThread(BaseModel):
    """A synthesized theme connecting facts, quantitative metrics, and forward catalysts."""
    theme_title: str
    core_thesis: str
    supporting_metrics: List[Dict[str, Any]]
    management_perspective: Optional[str] = None
    regulatory_or_risk_factor: Optional[str] = None
    synthesis_conclusion: str


class QuantitativeTriangulator:
    """Validates claims by cross-referencing across multiple independent tiers."""

    def __init__(self, minimum_sources_for_triangulation: int = 2):
        self.min_sources = minimum_sources_for_triangulation

    def triangulate(self, claim_name: str, observations: List[DataPoint]) -> TriangulationResult:
        """
        Evaluates a set of candidate observations for a claim across independent sources.
        """
        if not observations:
            return TriangulationResult(
                metric_or_claim=claim_name,
                verified=False,
                confidence_score=0.0,
                source_count=0,
                concordant_sources=[],
                conflicting_sources=[],
                verdict="SINGLE_SOURCE_UNCONFIRMED",
                narrative_explanation="No observation points supplied for triangulation.",
            )

        unique_sources = set(p.source_type for p in observations)
        source_count = len(unique_sources)

        # Baseline checks
        if source_count < self.min_sources:
            top_p = observations[0]
            return TriangulationResult(
                metric_or_claim=claim_name,
                verified=top_p.tier <= SourceTier.TIER_2_FINANCIAL_API,
                confidence_score=round(top_p.confidence * 0.85, 2),
                source_count=source_count,
                concordant_sources=list(unique_sources),
                conflicting_sources=[],
                verdict="SINGLE_SOURCE_UNCONFIRMED",
                narrative_explanation=(
                    f"Claim supported by a single source ({top_p.source_type}, Tier {top_p.tier}). "
                    f"Requires secondary independent corroboration for full triangulation."
                ),
            )

        # Check numerical congruence among sources
        primary_val = observations[0].value
        concordant = []
        conflicting = []

        for p in observations:
            if isinstance(primary_val, (int, float)) and isinstance(p.value, (int, float)):
                diff = abs(float(p.value) - float(primary_val)) / max(abs(float(primary_val)), 1.0)
                if diff <= 0.05:  # within 5%
                    concordant.append(p.source_type)
                else:
                    conflicting.append(p.source_type)
            elif str(primary_val).strip().lower() in str(p.value).strip().lower() or str(p.value).strip().lower() in str(primary_val).strip().lower():
                concordant.append(p.source_type)
            else:
                conflicting.append(p.source_type)

        concordant = list(set(concordant))
        conflicting = list(set(conflicting))

        if len(concordant) >= self.min_sources and not conflicting:
            # Multi-tier confirmation
            avg_conf = sum(p.confidence for p in observations) / len(observations)
            # Boost confidence for multi-source confirmation
            boosted_conf = min(1.0, round(avg_conf + 0.15, 2))
            return TriangulationResult(
                metric_or_claim=claim_name,
                verified=True,
                confidence_score=boosted_conf,
                source_count=source_count,
                concordant_sources=concordant,
                conflicting_sources=[],
                verdict="TRIANGULATED_CONFIRMED",
                narrative_explanation=(
                    f"Triangulated across {len(concordant)} independent sources ({', '.join(concordant)}). "
                    f"High confidence quantitative confirmation achieved."
                ),
            )
        elif conflicting:
            return TriangulationResult(
                metric_or_claim=claim_name,
                verified=False,
                confidence_score=0.45,
                source_count=source_count,
                concordant_sources=concordant,
                conflicting_sources=conflicting,
                verdict="CONTRADICTED",
                narrative_explanation=(
                    f"Contradiction detected between concordant sources ({', '.join(concordant)}) "
                    f"and conflicting sources ({', '.join(conflicting)}). Discrepancy logged for hierarchy resolution."
                ),
            )
        else:
            return TriangulationResult(
                metric_or_claim=claim_name,
                verified=True,
                confidence_score=0.75,
                source_count=source_count,
                concordant_sources=concordant,
                conflicting_sources=[],
                verdict="TRIANGULATED_CONFIRMED",
                narrative_explanation=f"Corroborated across {len(concordant)} sources.",
            )


class NarrativeThreader:
    """Connects siloed analytical data points into coherent investment narrative sections."""

    def build_narrative_thread(
        self,
        theme_title: str,
        core_thesis: str,
        supporting_metrics: List[Dict[str, Any]],
        management_perspective: Optional[str] = None,
        regulatory_or_risk_factor: Optional[str] = None,
        synthesis_conclusion: str = "",
    ) -> NarrativeThread:
        return NarrativeThread(
            theme_title=theme_title,
            core_thesis=core_thesis,
            supporting_metrics=supporting_metrics,
            management_perspective=management_perspective,
            regulatory_or_risk_factor=regulatory_or_risk_factor,
            synthesis_conclusion=synthesis_conclusion,
        )

    def render_thread_markdown(self, thread: NarrativeThread) -> str:
        """Renders an individual narrative thread in institutional investment report markdown."""
        lines = [
            f"### {thread.theme_title}",
            "",
            thread.core_thesis,
            "",
            "**Quantitative Substantiation:**",
        ]

        for m in thread.supporting_metrics:
            metric_lbl = m.get("metric", "Metric")
            val = m.get("value", "-")
            src = m.get("source", "Authoritative Source")
            notes = f" — *{m.get('notes')}*" if m.get("notes") else ""
            lines.append(f"- **{metric_lbl}:** {val} *(Source: {src})*{notes}")

        if thread.management_perspective:
            lines.append("")
            lines.append(f"**Executive Commentary & Strategic Guidance:**\n> \"{thread.management_perspective}\"")

        if thread.regulatory_or_risk_factor:
            lines.append("")
            lines.append(f"**Identified Risk / Counter-Evidence:**\n- {thread.regulatory_or_risk_factor}")

        if thread.synthesis_conclusion:
            lines.append("")
            lines.append(f"**Analyst Synthesis & Verdict:**\n{thread.synthesis_conclusion}")

        lines.append("")
        return "\n".join(lines)
