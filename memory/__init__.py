"""Memory package for ARA-1.

Implements the three-layer memory architecture:
1. Working Memory (Short-Term Context Management & Token Trimming)
2. Long-Term Semantic Memory (Chroma / Vector Database)
3. Episodic Memory (Research Strategy & Reflection Storage)
"""

from memory.vector_store import (
    FinancialVectorStore,
    ResearchDocument,
    SearchResult,
    EmbeddingGenerator,
    DocumentChunker,
)
from memory.context_manager import (
    ContextManager,
    ContextBudgetConfig,
)
from memory.episodic import (
    EpisodicMemoryStore,
    EpisodicRecord,
    ErrorRecoveryPath,
)

__all__ = [
    "FinancialVectorStore",
    "ResearchDocument",
    "SearchResult",
    "EmbeddingGenerator",
    "DocumentChunker",
    "ContextManager",
    "ContextBudgetConfig",
    "EpisodicMemoryStore",
    "EpisodicRecord",
    "ErrorRecoveryPath",
]

