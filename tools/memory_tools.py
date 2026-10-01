"""Memory Tool Integrations for ARA-1.

Implements real working versions of:
- VectorDbSearchTool (vector_db_search): Queries ChromaDB long-term memory with metadata filtering.
- VectorDbStoreTool (vector_db_store): Ingests and persists research findings with provenance tracking.
"""

from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from tools.tool_registry import BaseTool, ToolMetadata
from tools.schemas import VectorDbSearchInput, VectorDbStoreInput
from memory.vector_store import FinancialVectorStore, ResearchDocument

logger = logging.getLogger("ARA1.MemoryTools")


class VectorDbSearchTool(BaseTool):
    """Tool for semantic similarity searching across persistent research memory."""

    def __init__(self, vector_store: Optional[FinancialVectorStore] = None):
        metadata = ToolMetadata(
            name="vector_db_search",
            description=(
                "Searches the agent's long-term vector database memory for prior research findings, "
                "financial metrics, and SEC disclosure excerpts matching the semantic query. "
                "Supports optional metadata filtering by ticker and source_type."
            ),
            category="memory",
            rate_limit_rps=50.0,
            fallback_tools=[],
            unlocked=True,
            input_schema=VectorDbSearchInput,
        )
        super().__init__(metadata)
        self.vector_store = vector_store or FinancialVectorStore()

    def run(
        self,
        query: str,
        top_k: int = 5,
        limit: Optional[int] = None,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Executes similarity query against ChromaDB with optional metadata filtering."""
        effective_k = limit if limit is not None else top_k
        logger.info(f"Executing vector_db_search: query='{query}', top_k={effective_k}, filter={filter}")
        filter_dict = filter or {}

        ticker = filter_dict.get("ticker")
        source_type = filter_dict.get("source_type")
        min_conf = float(filter_dict.get("min_confidence", 0.0))

        results = self.vector_store.search(
            query=query,
            ticker=ticker,
            source_type=source_type,
            top_k=top_k,
            min_confidence=min_conf,
        )

        formatted_matches: List[Dict[str, Any]] = []
        for r in results:
            formatted_matches.append({
                "id": r.document.id,
                "content": r.document.content,
                "ticker": r.document.ticker,
                "source_type": r.document.source_type,
                "date": r.document.date,
                "similarity_score": r.similarity_score,
                "confidence": r.document.confidence,
                "verified": r.document.verified,
                "source_url": r.document.source_url,
                "metadata": r.document.metadata,
            })

        logger.info(f"vector_db_search retrieved {len(formatted_matches)} matching records.")
        return formatted_matches


class VectorDbStoreTool(BaseTool):
    """Tool for persisting verified research findings into long-term vector memory."""

    def __init__(self, vector_store: Optional[FinancialVectorStore] = None):
        metadata = ToolMetadata(
            name="vector_db_store",
            description=(
                "Persists structured research findings, verified metrics, or synthesized insights into the "
                "long-term vector database with full metadata (ticker, source_type, confidence, verified status)."
            ),
            category="memory",
            rate_limit_rps=50.0,
            fallback_tools=[],
            unlocked=True,
            input_schema=VectorDbStoreInput,
        )
        super().__init__(metadata)
        self.vector_store = vector_store or FinancialVectorStore()

    def run(
        self,
        content: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Persists content and metadata into ChromaDB vector memory."""
        meta = metadata or {}
        ticker = str(meta.get("ticker", "GEN")).upper().strip()
        source_type = str(meta.get("source_type", "research_finding")).strip()
        doc_id = meta.get("id") or f"{ticker.lower()}-{source_type.lower()}-{uuid.uuid4().hex[:8]}"
        date_val = meta.get("date") or datetime.now(timezone.utc).isoformat()
        confidence = float(meta.get("confidence", 0.90))
        verified = bool(meta.get("verified", False))
        session_id = str(meta.get("researcher_session", "ara1_session"))
        source_url = meta.get("source_url")

        extra_meta = {k: v for k, v in meta.items() if k not in (
            "ticker", "source_type", "id", "date", "confidence", "verified", "researcher_session", "source_url"
        )}

        doc = ResearchDocument(
            id=doc_id,
            content=content.strip(),
            ticker=ticker,
            source_type=source_type,
            date=date_val,
            confidence=confidence,
            verified=verified,
            researcher_session=session_id,
            source_url=source_url,
            metadata=extra_meta,
        )

        saved_id = self.vector_store.add_document(doc)
        logger.info(f"vector_db_store persisted document id='{saved_id}' for ticker='{ticker}'")

        return {
            "status": "stored",
            "document_id": saved_id,
            "ticker": ticker,
            "source_type": source_type,
            "confidence": confidence,
            "verified": verified,
            "message": f"Successfully stored research record '{saved_id}' in long-term vector memory.",
        }
