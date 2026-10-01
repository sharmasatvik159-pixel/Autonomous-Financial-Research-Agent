"""Disambiguation Engine & Edge-Case Intelligence for ARA-1.

Implements:
1. Documented assumptions generator for underspecified or vague queries.
2. Clarifying question framework for interactive or semi-autonomous workflows.
3. Edge-case handling strategies:
   - Private companies without SEC filings (OpenAI, Stripe, SpaceX)
   - Recent IPOs with truncated financial history (Arm, Reddit)
   - Rapid corporate changes (M&A, restructuring, tender offers, regulatory investigations)
"""

from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from agent.query_analyzer import (
    QueryAnalysisResult,
    QueryScope,
    AmbiguityLevel,
    EntityLifecycle,
)

logger = logging.getLogger("ARA1.QueryIntelligence.Disambiguation")


class EdgeCaseGuidance(BaseModel):
    """Specific routing and constraint instructions for special entity types."""
    entity_name: str
    lifecycle: EntityLifecycle
    sec_filings_available: bool
    recommended_tools: List[str]
    caution_notes: List[str]
    confidence_penalty: float = 0.0
    alternative_proxies: List[str] = Field(default_factory=list)


class DisambiguationPlan(BaseModel):
    """Complete disambiguation artifact for execution and logging."""
    raw_query: str
    ambiguity_level: AmbiguityLevel
    documented_assumptions: List[str]
    clarifying_questions: List[str]
    edge_case_guidance: Optional[EdgeCaseGuidance] = None
    preamble_markdown: str


class DisambiguationEngine:
    """Generates explicit operational assumptions and handles specialized corporate edge cases."""

    def __init__(self):
        pass

    def disambiguate(self, analysis: QueryAnalysisResult) -> DisambiguationPlan:
        """Constructs documented assumptions, clarifying questions, and edge-case instructions."""
        assumptions = self.generate_assumptions(analysis)
        questions = self.generate_clarifying_questions(analysis)
        edge_guidance = self.evaluate_edge_cases(analysis)
        preamble = self.generate_disambiguation_preamble(analysis, assumptions, edge_guidance)

        return DisambiguationPlan(
            raw_query=analysis.raw_query,
            ambiguity_level=analysis.ambiguity_level,
            documented_assumptions=assumptions,
            clarifying_questions=questions,
            edge_case_guidance=edge_guidance,
            preamble_markdown=preamble,
        )

    def generate_assumptions(self, analysis: QueryAnalysisResult) -> List[str]:
        """Formulates concrete, institutional operating assumptions to resolve missing dimensions."""
        assumptions = []

        # 1. Geographic Assumption
        if "Geographic Jurisdiction" in analysis.missing_dimensions:
            assumptions.append(
                "**Geographic Scope:** Inferred primary jurisdiction as United States capital markets and SEC regulatory oversight, with cross-border linkages evaluated where relevant."
            )

        # 2. Entity / Benchmark Cohort Assumption
        if "Target Entity or Sector Specificity" in analysis.missing_dimensions:
            if "Financials" in analysis.target_sectors or "banks" in analysis.cleaned_query.lower():
                assumptions.append(
                    "**Entity Universe:** Bifurcated the cohort into Tier 1 Global Systemically Important Banks (G-SIBs: JPM, BAC, WFC, C) versus Super-Regional lenders ($50B–$250B assets, KRE index)."
                )
            elif "Technology" in analysis.target_sectors or "tech" in analysis.cleaned_query.lower():
                assumptions.append(
                    "**Entity Universe:** Selected bellwether technology leaders representing enterprise software, hyperscale cloud, and AI infrastructure (MSFT, AAPL, GOOGL, AMZN, PLTR)."
                )
            else:
                assumptions.append(
                    "**Entity Universe:** Benchmarked against leading large-cap S&P 500 constituents in the inferred economic sector."
                )
        elif "Constituent Institutional Tickers" in analysis.missing_dimensions and analysis.target_sectors:
            sector = analysis.target_sectors[0]
            assumptions.append(
                f"**Constituent Cohort:** Sampled representative market-cap leaders in the {sector} sector to evaluate prevailing structural themes."
            )

        # 3. Temporal Horizon Assumption
        if "Temporal Horizon / Fiscal Period" in analysis.missing_dimensions:
            assumptions.append(
                "**Temporal Horizon:** Focused on the trailing twelve months (TTM) and current fiscal year, contextualized by a 3-year historical trend."
            )

        # 4. Metric Focus Assumption
        if "Target Metric or Valuation Vector" in analysis.missing_dimensions:
            if "Financials" in analysis.target_sectors or "banks" in analysis.cleaned_query.lower():
                assumptions.append(
                    "**Analytical Vector:** Evaluated Net Interest Income (NII) compression, deposit betas, unrealized bond losses (AFS/HTM), CRE loan provisions, and CET1 capital ratios."
                )
            else:
                assumptions.append(
                    "**Analytical Vector:** Evaluated fundamental revenue growth, operating margin expansion, capital expenditure intensity, and peer valuation multiples."
                )

        # Fallback if no specific missing dimensions were flagged
        if not assumptions:
            assumptions.append(
                "**Standard Baseline:** Standardized on audited SEC statutory disclosures, consensus Wall Street multiples, and verified historical filings."
            )

        return assumptions

    def generate_clarifying_questions(self, analysis: QueryAnalysisResult) -> List[str]:
        """Generates targeted clarifying questions for interactive human-in-the-loop refinement."""
        questions = []
        q_lower = analysis.cleaned_query.lower()

        if "banks" in q_lower or "financial" in q_lower:
            questions.append("Would you prefer to focus specifically on money-center G-SIBs (e.g., JPM, BAC) or regional lenders exposed to Commercial Real Estate?")
            questions.append("Are you primarily interested in liquidity/capital adequacy (CET1, unrealized HTM losses) or operating earnings (NII compression, deposit costs)?")
        elif "tech" in q_lower or "software" in q_lower or "cloud" in q_lower:
            questions.append("Which technology subsector do you wish to prioritize: enterprise SaaS, hyperscale cloud providers, or semiconductor hardware?")
            questions.append("Should this analysis examine valuation multiples (EV/Sales, P/E) or underlying operational catalysts (GenAI infrastructure CapEx, enterprise adoption)?")
        else:
            if not analysis.extracted_tickers:
                questions.append("Which specific ticker symbols or corporate entities would you like prioritized in this research?")
            questions.append("What specific time horizon or fiscal reporting period should this investigation target?")
            questions.append("Are there specific risk vectors (e.g., credit risk, antitrust, margin compression) you want deep-dived?")

        return questions

    def evaluate_edge_cases(self, analysis: QueryAnalysisResult) -> Optional[EdgeCaseGuidance]:
        """Provides specialized operational routing when encountering non-standard corporate profiles."""
        # 1. Private Company Edge Case
        if analysis.lifecycle_status == EntityLifecycle.PRIVATE_COMPANY:
            entity = analysis.extracted_entities[0] if analysis.extracted_entities else "Target Private Entity"
            return EdgeCaseGuidance(
                entity_name=entity,
                lifecycle=EntityLifecycle.PRIVATE_COMPANY,
                sec_filings_available=False,
                recommended_tools=["web_search", "news_sentiment", "peer_comparison"],
                caution_notes=[
                    "No statutory SEC Form 10-K or 10-Q filings exist for private entities.",
                    "Valuation metrics must rely on venture funding rounds (Series A/B/C/D), PitchBook/Crunchbase press reports, or secondary liquidity platforms (Forge, EquityZen).",
                    "Financial statements are unaudited and subject to selective disclosure bias.",
                ],
                confidence_penalty=0.35,
                alternative_proxies=["Publicly traded enterprise software peers", "S&P 500 Software & Services Industry Group"],
            )

        # 2. Recent IPO Edge Case
        if analysis.lifecycle_status == EntityLifecycle.RECENT_IPO:
            entity = analysis.extracted_entities[0] if analysis.extracted_entities else "Recent IPO Entity"
            return EdgeCaseGuidance(
                entity_name=entity,
                lifecycle=EntityLifecycle.RECENT_IPO,
                sec_filings_available=True,
                recommended_tools=["sec_filing_search", "web_search", "financial_data_api"],
                caution_notes=[
                    "Limited statutory 10-K history; primary baseline filing is Form S-1 / Prospectus.",
                    "Historical multi-year CAGR calculations may be unrepresentative due to pre-IPO restructuring.",
                    "Evaluate upcoming share lock-up expiration dates and dual-class voting share structures.",
                ],
                confidence_penalty=0.15,
                alternative_proxies=["Mature industry incumbents for multiple benchmarking"],
            )

        # 3. Rapid Corporate Change / Distressed M&A
        if analysis.rate_of_change_flag or analysis.lifecycle_status == EntityLifecycle.DISTRESSED_MA:
            entity = analysis.extracted_entities[0] if analysis.extracted_entities else "Target Entity"
            return EdgeCaseGuidance(
                entity_name=entity,
                lifecycle=EntityLifecycle.DISTRESSED_MA,
                sec_filings_available=True,
                recommended_tools=["news_sentiment", "web_search", "sec_filing_search"],
                caution_notes=[
                    "HIGH TEMPORAL SENSITIVITY: Static trailing 10-K financial metrics may be obsolete.",
                    "Prioritize Form 8-K Current Reports, press releases, and real-time wire feeds over historical 10-K.",
                    "Check transaction break fees, regulatory antitrust approvals, and debt covenants.",
                ],
                confidence_penalty=0.20,
                alternative_proxies=["Acquiring entity or target peer comps"],
            )

        return None

    def generate_disambiguation_preamble(
        self,
        analysis: QueryAnalysisResult,
        assumptions: List[str],
        edge_guidance: Optional[EdgeCaseGuidance] = None,
    ) -> str:
        """Formats an institutional Markdown preamble documenting assumptions and edge-case caveats."""
        lines = [
            "> [!NOTE]",
            f"> ### Query Disambiguation & Documented Assumptions",
            f"> **Raw Inquest:** *\"{analysis.raw_query}\"*  ",
            f"> **Classification:** Scope: `{analysis.scope.value}` | Complexity: `{analysis.complexity.value}` | Ambiguity Score: `{analysis.ambiguity_score}/1.0` ({analysis.ambiguity_level.value})  ",
        ]

        if assumptions:
            lines.append("> **Documented Operational Assumptions:**")
            for asm in assumptions:
                lines.append(f"> - {asm}")

        if edge_guidance:
            lines.append(f"> **Special Corporate Profile [{edge_guidance.lifecycle.value}]:**")
            for note in edge_guidance.caution_notes:
                lines.append(f"> - ⚠️ *{note}*")
            if edge_guidance.alternative_proxies:
                lines.append(f"> - **Benchmarking Proxies:** {', '.join(edge_guidance.alternative_proxies)}")

        lines.append("")
        return "\n".join(lines)


_GLOBAL_DISAMBIGUATION_ENGINE: Optional[DisambiguationEngine] = None


def get_disambiguation_engine() -> DisambiguationEngine:
    """Retrieves or initializes the global DisambiguationEngine singleton."""
    global _GLOBAL_DISAMBIGUATION_ENGINE
    if _GLOBAL_DISAMBIGUATION_ENGINE is None:
        _GLOBAL_DISAMBIGUATION_ENGINE = DisambiguationEngine()
    return _GLOBAL_DISAMBIGUATION_ENGINE
