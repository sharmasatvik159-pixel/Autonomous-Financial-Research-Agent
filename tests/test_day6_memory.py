"""Day 6 Memory Architecture & Retrieval Verification Test Suite.

Tests 3-Layer Memory components:
- memory/vector_store.py: DocumentChunker (section-aware, Q&A pairs) and FinancialVectorStore (ChromaDB)
- memory/context_manager.py: Progressive summarization & selective retention for context window limits
- memory/episodic.py: Procedural episodic memory, strategy retrieval, error recovery paths
- tools/memory_tools.py: vector_db_search and vector_db_store integrated into ToolRegistry
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from memory.vector_store import FinancialVectorStore, ResearchDocument, DocumentChunker
from memory.context_manager import ContextManager, ContextBudgetConfig
from memory.episodic import EpisodicMemoryStore, EpisodicRecord, ErrorRecoveryPath
from tools.memory_tools import VectorDbSearchTool, VectorDbStoreTool
from tools.tool_registry import ToolRegistry


@pytest.fixture
def temp_store_dir():
    temp_dir = tempfile.mkdtemp(prefix="ara1_day6_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_document_chunker_section_aware():
    """Verify section-aware chunking for SEC filings and Q&A speaker pair chunking for transcripts."""
    # 1. SEC Filing chunking
    filing_text = (
        "ITEM 1. BUSINESS\n"
        "Microsoft develops enterprise software and cloud platforms.\n\n"
        "ITEM 1A. RISK FACTORS\n"
        "Intense competition in cloud infrastructure and AI models could compress margins.\n"
        "Cybersecurity threats may compromise enterprise client data integrity.\n\n"
        "ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS\n"
        "Intelligent Cloud revenue grew 19% driven by Azure enterprise expansion.\n"
    )
    filing_chunks = DocumentChunker.chunk_sec_filing(
        text=filing_text,
        ticker="MSFT",
        filing_type="10-K",
        year=2024,
    )
    assert len(filing_chunks) >= 3
    tags = [c.metadata.get("section_tag") for c in filing_chunks]
    assert "item1" in tags
    assert "item1a" in tags
    assert "item7" in tags

    # 2. Earnings Call Q&A speaker pairs
    transcript_text = (
        "Satya Nadella: Welcome everyone. We had a record quarter driven by Microsoft Cloud.\n\n"
        "Questions and Answers Session\n\n"
        "Keith Weiss (Morgan Stanley): Could you comment on the growth contribution from Azure OpenAI?\n"
        "Satya Nadella: Demand continues to be higher than our available capacity.\n"
    )
    qa_chunks = DocumentChunker.chunk_earnings_transcript(
        text=transcript_text,
        ticker="MSFT",
        quarter="Q4",
        year=2024,
    )
    assert len(qa_chunks) >= 1
    assert any("Keith Weiss" in c.content for c in qa_chunks)


def test_vector_store_schema_and_retrieval(temp_store_dir):
    """Verify storing test research documents, metadata tagging, and semantic vector retrieval."""
    store = FinancialVectorStore(persist_directory=temp_store_dir, collection_name="test_day6_col")

    doc1 = ResearchDocument(
        id="msft-ai-001",
        content="Microsoft Azure OpenAI service adoption accelerating across Fortune 500 enterprises with strong Copilot ARPU expansion.",
        ticker="MSFT",
        source_type="analysis",
        date="2024-07-30",
        confidence=0.95,
        verified=True,
    )
    doc2 = ResearchDocument(
        id="aapl-srv-001",
        content="Apple Services segment revenue expanded to record highs driven by App Store and iCloud subscriptions.",
        ticker="AAPL",
        source_type="earnings_call",
        date="2024-08-01",
        confidence=0.90,
        verified=True,
    )
    doc3 = ResearchDocument(
        id="tsla-risk-001",
        content="Tesla automotive gross margin contracted due to aggressive EV price reductions in mainland China.",
        ticker="TSLA",
        source_type="10-K",
        date="2024-01-29",
        confidence=0.92,
        verified=True,
    )

    store.add_documents([doc1, doc2, doc3])
    assert store.count() == 3

    # Semantic query with ticker filter
    results = store.search("Azure OpenAI enterprise Copilot", ticker="MSFT", top_k=2)
    assert len(results) > 0
    top = results[0].document
    assert top.ticker == "MSFT"
    assert "Azure OpenAI" in top.content
    assert top.verified is True
    assert top.confidence >= 0.90

    # Query with source_type filter
    tsla_results = store.search("automotive gross margin price cuts", source_type="10-K", top_k=2)
    assert len(tsla_results) > 0
    assert tsla_results[0].document.ticker == "TSLA"
    store.close()


def test_context_window_compression():
    """Verify progressive summarization and observation compaction for large text blocks."""
    cm = ContextManager(config=ContextBudgetConfig(max_history_tokens=100, preserve_recent_steps=1))

    large_observation = {
        "ticker": "MSFT",
        "annual_metrics": [
            {"year": "FY24", "revenue": "$245.12B", "operating_margin": "44.6%"},
            {"year": "FY23", "revenue": "$211.91B", "operating_margin": "41.8%"},
        ]
    }

    # Verify structured JSON compaction to Markdown table
    compacted = cm.compact_observation(large_observation)
    assert "| year | revenue | operating_margin |" in compacted
    assert "$245.12B" in compacted

    # Verify progressive summarization
    history = [
        "Research Query: Microsoft revenue breakdown",
        "Thought: Step 1 find profile",
        "Action: company_profile",
        "Action Input: {'ticker': 'MSFT'}",
        "Observation: Microsoft Corporation develops software and Azure cloud services with $3.1T market cap.",
        "Thought: Step 2 find revenue",
        "Action: financial_data_api",
        "Action Input: {'ticker': 'MSFT'}",
        "Observation: FY24 revenue was $245.12 Billion up 15.7% YoY with $88.14 Billion net income.",
        "Thought: Step 3 finalize analysis",
    ]
    managed = cm.manage_context(history, force_summary=True)
    joined = "\n".join(managed)
    assert "PROGRESSIVE SUMMARY OF EARLIER RESEARCH STEPS" in joined
    assert "Thought: Step 3 finalize analysis" in joined


def test_episodic_memory_and_strategy_store(temp_store_dir):
    """Verify episodic memory recording, strategy retrieval, and error recovery paths."""
    store_file = Path(temp_store_dir) / "test_episodes.json"
    episodic = EpisodicMemoryStore(persist_path=str(store_file))

    # Record episode
    ep = EpisodicRecord(
        query="Analyze Apple quarterly earnings vs consensus",
        query_type="earnings_analysis",
        target_ticker="AAPL",
        tool_sequence=["financial_data_api", "sec_filing_search", "news_sentiment", "web_search"],
        successful_plan=["Pull financial statements", "Verify 10-Q filing", "Score news sentiment", "Search consensus"],
        reflection="High quality consensus comparison achieved.",
        outcome_quality=0.95,
    )
    rec_id = episodic.record_episode(ep)
    assert rec_id.startswith("ep-")

    # Retrieve similar strategy
    matches = episodic.retrieve_strategy("Apple quarterly earnings review", target_ticker="AAPL")
    assert len(matches) > 0
    top = matches[0]
    assert "financial_data_api" in top.tool_sequence

    # Record error recovery path
    episodic.record_error_recovery(
        failed_tool="earnings_transcript",
        error_message="rate_limit_exceeded",
        recovery_tool="web_search",
        recovery_action="Query company investor relations website via web_search",
        success=True,
    )
    recs = episodic.get_recovery_recommendations("earnings_transcript")
    assert len(recs) >= 1
    assert any(r.recovery_tool == "web_search" for r in recs)


def test_memory_tools_registry_integration(temp_store_dir):
    """Verify vector_db_store and vector_db_search tools operating inside ToolRegistry."""
    store = FinancialVectorStore(persist_directory=temp_store_dir, collection_name="registry_col")
    search_tool = VectorDbSearchTool(vector_store=store)
    store_tool = VectorDbStoreTool(vector_store=store)

    registry = ToolRegistry()
    registry.register_tool(search_tool)
    registry.register_tool(store_tool)

    # Store via registry
    store_res = registry.execute(
        "vector_db_store",
        {
            "content": "Google Cloud Platform reached $36B annualized run-rate with positive operating income.",
            "metadata": {
                "ticker": "GOOGL",
                "source_type": "10-K",
                "date": "2024-02-01",
                "confidence": 0.95,
                "verified": True,
            },
        },
    )
    assert store_res.success is True

    # Search via registry
    search_res = registry.execute(
        "vector_db_search",
        {
            "query": "Google Cloud operating income run-rate",
            "ticker": "GOOGL",
            "top_k": 1,
        },
    )
    assert search_res.success is True
    hits = search_res.data if isinstance(search_res.data, list) else search_res.data.get("results", [])
    assert len(hits) == 1
    assert "Google Cloud" in hits[0]["content"]
    store.close()
