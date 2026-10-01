"""Query Intelligence & Classification Engine for ARA-1.

Implements deep query classification across:
1. Scope: SINGLE_COMPANY, PEER_GROUP, SECTOR_INDUSTRY, MACRO_THEMATIC, REGULATORY
2. Complexity: SIMPLE_FACTUAL, COMPARATIVE_MULTI_ENTITY, CONTRADICTORY_SYNTHESIS, DEEP_THEMATIC_RESEARCH
3. Ambiguity Level: CLEAR, MODERATE, HIGH, CRITICAL
4. Edge Case Detection: Private companies, recent IPOs, rapid corporate changes (M&A, restructuring)
"""

from __future__ import annotations
import re
import logging
from enum import Enum
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field

logger = logging.getLogger("ARA1.QueryIntelligence.Analyzer")

class QueryScope(str, Enum):
    SINGLE_COMPANY = "SINGLE_COMPANY"
    PEER_GROUP = "PEER_GROUP"
    SECTOR_INDUSTRY = "SECTOR_INDUSTRY"
    MACRO_THEMATIC = "MACRO_THEMATIC"
    REGULATORY = "REGULATORY"
    UNKNOWN = "UNKNOWN"

class QueryComplexity(str, Enum):
    SIMPLE_FACTUAL = "SIMPLE_FACTUAL"
    COMPARATIVE_MULTI_ENTITY = "COMPARATIVE_MULTI_ENTITY"
    CONTRADICTORY_SYNTHESIS = "CONTRADICTORY_SYNTHESIS"
    DEEP_THEMATIC_RESEARCH = "DEEP_THEMATIC_RESEARCH"

class AmbiguityLevel(str, Enum):
    CLEAR = "CLEAR"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class EntityLifecycle(str, Enum):
    PUBLIC_MATURE = "PUBLIC_MATURE"
    RECENT_IPO = "RECENT_IPO"
    PRIVATE_COMPANY = "PRIVATE_COMPANY"
    DISTRESSED_MA = "DISTRESSED_MA"
    UNKNOWN = "UNKNOWN"

class QueryAnalysisResult(BaseModel):
    """Structured assessment produced by QueryAnalyzer."""
    raw_query: str
    cleaned_query: str
    scope: QueryScope
    complexity: QueryComplexity
    ambiguity_level: AmbiguityLevel
    ambiguity_score: float = Field(ge=0.0, le=1.0)
    is_ambiguous: bool
    extracted_tickers: List[str] = Field(default_factory=list)
    extracted_entities: List[str] = Field(default_factory=list)
    target_sectors: List[str] = Field(default_factory=list)
    missing_dimensions: List[str] = Field(default_factory=list)
    detected_edge_cases: List[str] = Field(default_factory=list)
    lifecycle_status: EntityLifecycle = EntityLifecycle.PUBLIC_MATURE
    rate_of_change_flag: bool = False
    requires_memory_synthesis: bool = False
    recommended_strategy: str = "REACT_STANDARD"

class QueryAnalyzer:
    """Classifies financial research queries for ambiguity, complexity, and special edge cases."""

    TICKER_REGEX = re.compile(r"(?:\$|\b)([A-Z]{1,5})\b")

    KNOWN_TICKERS: Dict[str, str] = {
        "MICROSOFT": "MSFT", "APPLE": "AAPL", "TESLA": "TSLA",
        "AMAZON": "AMZN", "GOOGLE": "GOOGL", "ALPHABET": "GOOGL",
        "PALANTIR": "PLTR", "NVIDIA": "NVDA", "META": "META",
        "JPMORGAN": "JPM", "BANK OF AMERICA": "BAC", "WELLS FARGO": "WFC",
        "CITIGROUP": "C", "CITI": "C", "NEW YORK COMMUNITY BANCORP": "NYCB",
    }

    KNOWN_PRIVATE_ENTITIES: Set[str] = {
        "OPENAI", "STRIPE", "BYTEDANCE", "SPACEX", "ANTHROPIC",
        "DATABRICKS", "CANVA", "EPIC GAMES", "REVOLUT", "CHIME",
    }

    KNOWN_RECENT_IPOS: Set[str] = {
        "ARM", "REDDIT", "RDDT", "BIRKENSTOCK", "BIRK", "INSTACART", "CART",
        "KLARNA", "RUBRIK", "RBRK", "TEMU",
    }

    SECTOR_KEYWORDS: Dict[str, List[str]] = {
        "Technology": ["tech", "technology", "software", "cloud", "saas", "hardware", "semiconductor", "ai", "artificial intelligence"],
        "Financials": ["bank", "banks", "banking", "financial", "fintech", "insurance", "brokerage", "lending", "credit"],
        "Automotive": ["auto", "electric vehicle", "ev", "automotive", "car maker"],
        "Energy": ["oil", "gas", "energy", "solar", "renewable", "clean energy"],
        "Healthcare": ["biotech", "pharma", "pharmaceutical", "healthcare", "medical device"],
    }

    RAPID_CHANGE_KEYWORDS: List[str] = [
        "acquisition", "merger", "buyout", "takeover", "tender offer",
        "bankruptcy", "chapter 11", "restructuring", "default", "liquidation",
        "fraud", "investigation", "sec probe", "doj probe", "hostile bid",
        "activist", "spin-off", "spinoff", "proxy fight", "sudden departure",
    ]

    VAGUE_PATTERNS: List[re.Pattern] = [
        re.compile(r"^what(?:'s| is) happening with (.+)\??$", re.IGNORECASE),
        re.compile(r"^how (?:are|is) (.+) doing\??$", re.IGNORECASE),
        re.compile(r"^tell me about (.+)$", re.IGNORECASE),
        re.compile(r"^what about (.+)$", re.IGNORECASE),
        re.compile(r"^look into (.+)$", re.IGNORECASE),
        re.compile(r"^give me an update on (.+)$", re.IGNORECASE),
    ]

    def __init__(self):
        pass

    def analyze(self, query: str) -> QueryAnalysisResult:
        """Performs comprehensive linguistic, domain, and entity analysis on a research query."""
        raw_query = query.strip()
        cleaned_query = " ".join(raw_query.split())
        query_upper = cleaned_query.upper()

        extracted_tickers = self._extract_tickers(cleaned_query)
        extracted_entities = self._extract_named_entities(cleaned_query)

        detected_sectors = []
        for sector, kws in self.SECTOR_KEYWORDS.items():
            if any(re.search(rf"\b{re.escape(kw)}\b", cleaned_query, re.IGNORECASE) for kw in kws):
                detected_sectors.append(sector)

        detected_edge_cases = []
        lifecycle = EntityLifecycle.PUBLIC_MATURE

        for private_co in self.KNOWN_PRIVATE_ENTITIES:
            if private_co in query_upper:
                detected_edge_cases.append(f"PRIVATE_COMPANY:{private_co}")
                lifecycle = EntityLifecycle.PRIVATE_COMPANY

        for recent_ipo in self.KNOWN_RECENT_IPOS:
            if recent_ipo in query_upper or any(t == recent_ipo for t in extracted_tickers):
                detected_edge_cases.append(f"RECENT_IPO:{recent_ipo}")
                lifecycle = EntityLifecycle.RECENT_IPO

        rate_of_change = any(
            re.search(rf"\b{re.escape(kw)}\b", cleaned_query, re.IGNORECASE)
            for kw in self.RAPID_CHANGE_KEYWORDS
        )
        if rate_of_change:
            detected_edge_cases.append("RAPID_CORPORATE_CHANGE")
            if lifecycle == EntityLifecycle.PUBLIC_MATURE:
                lifecycle = EntityLifecycle.DISTRESSED_MA

        scope = self._classify_scope(cleaned_query, extracted_tickers, detected_sectors)

        complexity = self._classify_complexity(cleaned_query, scope)

        ambiguity_level, ambiguity_score, missing_dimensions = self._assess_ambiguity(
            cleaned_query, extracted_tickers, detected_sectors, scope
        )

        requires_memory = bool(
            re.search(r"already researched|previous(?:ly)? researched|in your memory|vector memory|past research", cleaned_query, re.IGNORECASE)
            or (scope == QueryScope.SECTOR_INDUSTRY and "theme" in cleaned_query.lower())
        )

        strategy = "REACT_STANDARD"
        if requires_memory:
            strategy = "MEMORY_DRIVEN_SECTOR_SYNTHESIS"
        elif ambiguity_level in (AmbiguityLevel.HIGH, AmbiguityLevel.CRITICAL):
            strategy = "REACT_WITH_DISAMBIGUATION"
        elif complexity == QueryComplexity.CONTRADICTORY_SYNTHESIS:
            strategy = "CONTRADICTION_RECONCILIATION"
        elif scope == QueryScope.PEER_GROUP:
            strategy = "COMPARATIVE_PEER_MATRIX"

        return QueryAnalysisResult(
            raw_query=raw_query,
            cleaned_query=cleaned_query,
            scope=scope,
            complexity=complexity,
            ambiguity_level=ambiguity_level,
            ambiguity_score=round(ambiguity_score, 2),
            is_ambiguous=ambiguity_score >= 0.5,
            extracted_tickers=extracted_tickers,
            extracted_entities=extracted_entities,
            target_sectors=detected_sectors,
            missing_dimensions=missing_dimensions,
            detected_edge_cases=detected_edge_cases,
            lifecycle_status=lifecycle,
            rate_of_change_flag=rate_of_change,
            requires_memory_synthesis=requires_memory,
            recommended_strategy=strategy,
        )

    def _extract_tickers(self, query: str) -> List[str]:
        """Extracts valid capitalized stock ticker candidates."""
        matches = self.TICKER_REGEX.findall(query)
        blacklist = {"A", "I", "AND", "OR", "THE", "FOR", "IN", "ON", "WHAT", "HOW", "WITH", "IS", "ARE", "OF", "TO", "SEC", "CEO", "CFO", "DCF", "PE", "EPS", "ROE"}
        valid_tickers = [m for m in matches if m not in blacklist and len(m) <= 5]

        query_upper = query.upper()
        for name, ticker in self.KNOWN_TICKERS.items():
            if name in query_upper and ticker not in valid_tickers:
                valid_tickers.append(ticker)

        return list(dict.fromkeys(valid_tickers))

    def _extract_named_entities(self, query: str) -> List[str]:
        """Extracts recognizable companies or industry entities."""
        entities = []
        query_upper = query.upper()
        for name in list(self.KNOWN_TICKERS.keys()) + list(self.KNOWN_PRIVATE_ENTITIES) + list(self.KNOWN_RECENT_IPOS):
            if name in query_upper:
                entities.append(name.title())
        return list(dict.fromkeys(entities))

    def _classify_scope(self, query: str, tickers: List[str], sectors: List[str]) -> QueryScope:
        """Determines the operational scope of the query."""
        q_lower = query.lower()

        if "regulatory" in q_lower or "dodd-frank" in q_lower or "scap" in q_lower or "basel" in q_lower:
            return QueryScope.REGULATORY
        if "across" in q_lower or "sector" in q_lower or "industry" in q_lower:
            return QueryScope.SECTOR_INDUSTRY
        if len(tickers) > 1 or "compare" in q_lower or "peer" in q_lower or "versus" in q_lower or " vs " in q_lower:
            return QueryScope.PEER_GROUP
        if len(tickers) == 1:
            return QueryScope.SINGLE_COMPANY
        if sectors:
            return QueryScope.SECTOR_INDUSTRY
        if any(pat.match(query) for pat in self.VAGUE_PATTERNS):
            return QueryScope.MACRO_THEMATIC

        return QueryScope.MACRO_THEMATIC

    def _classify_complexity(self, query: str, scope: QueryScope) -> QueryComplexity:
        """Assigns complexity rating based on analytical requirements."""
        q_lower = query.lower()
        if "contradiction" in q_lower or "contradictory" in q_lower or "conflict" in q_lower or "reconcil" in q_lower:
            return QueryComplexity.CONTRADICTORY_SYNTHESIS
        if scope in (QueryScope.SECTOR_INDUSTRY, QueryScope.MACRO_THEMATIC) or "themes" in q_lower or "cross-cutting" in q_lower:
            return QueryComplexity.DEEP_THEMATIC_RESEARCH
        if scope == QueryScope.PEER_GROUP or "compare" in q_lower:
            return QueryComplexity.COMPARATIVE_MULTI_ENTITY
        if any(term in q_lower for term in ["revenue", "eps", "pe ratio", "price", "market cap", "ceo"]) and len(query.split()) < 10:
            return QueryComplexity.SIMPLE_FACTUAL
        return QueryComplexity.DEEP_THEMATIC_RESEARCH

    def _assess_ambiguity(
        self, query: str, tickers: List[str], sectors: List[str], scope: QueryScope
    ) -> tuple[AmbiguityLevel, float, List[str]]:
        """Calculates ambiguity score and enumerates missing dimensions."""
        missing = []
        score = 0.0

        is_vague_pattern = any(pat.match(query) for pat in self.VAGUE_PATTERNS)
        if is_vague_pattern:
            score += 0.45

        if not tickers and not sectors:
            score += 0.35
            missing.append("Target Entity or Sector Specificity")
        elif not tickers and sectors:
            score += 0.15
            missing.append("Constituent Institutional Tickers")

        has_time = any(w in query.lower() for w in ["q1", "q2", "q3", "q4", "2023", "2024", "2025", "2026", "fy", "ttm", "recent", "annual", "quarterly"])
        if not has_time:
            score += 0.15
            missing.append("Temporal Horizon / Fiscal Period")

        has_geo = any(w in query.lower() for w in ["us", "usa", "europe", "european", "asia", "china", "global", "india"])
        if not has_geo:
            score += 0.10
            missing.append("Geographic Jurisdiction")

        has_metrics = any(w in query.lower() for w in ["margin", "revenue", "valuation", "ratio", "risk", "growth", "dcf", "roe", "nii", "cre"])
        if not has_metrics:
            score += 0.15
            missing.append("Target Metric or Valuation Vector")

        score = min(score, 1.0)

        if score >= 0.70:
            level = AmbiguityLevel.CRITICAL
        elif score >= 0.45:
            level = AmbiguityLevel.HIGH
        elif score >= 0.25:
            level = AmbiguityLevel.MODERATE
        else:
            level = AmbiguityLevel.CLEAR

        return level, score, missing

_GLOBAL_QUERY_ANALYZER: Optional[QueryAnalyzer] = None

def get_query_analyzer() -> QueryAnalyzer:
    """Retrieves or initializes the global QueryAnalyzer singleton."""
    global _GLOBAL_QUERY_ANALYZER
    if _GLOBAL_QUERY_ANALYZER is None:
        _GLOBAL_QUERY_ANALYZER = QueryAnalyzer()
    return _GLOBAL_QUERY_ANALYZER
