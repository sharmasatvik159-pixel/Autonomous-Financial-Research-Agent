"""Unit tests for FinancialVectorStore and document schema."""

import pytest
import tempfile
import shutil
from memory.vector_store import FinancialVectorStore, ResearchDocument


@pytest.fixture
def temp_vector_store():
    """Provides a temporary vector store instance cleaned up after test execution."""
    tmp_dir = tempfile.mkdtemp()
    store = FinancialVectorStore(persist_directory=tmp_dir, collection_name="unit_test_memory")
    yield store
    store.close()
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_vector_store_add_and_count(temp_vector_store):
    """Verify document insertion and count tracking."""
    store = temp_vector_store
    assert store.count() == 0

    doc1 = ResearchDocument(
        id="nvda-10k-2024-001",
        content="NVIDIA Data Center revenue surged 427% driven by Hopper GPU architecture demand.",
        ticker="NVDA",
        source_type="10-K",
        confidence=0.99,
        verified=True
    )
    doc2 = ResearchDocument(
        id="aapl-10k-2024-001",
        content="Apple Services revenue set an all-time record of $85 billion.",
        ticker="AAPL",
        source_type="10-K",
        confidence=0.95,
        verified=True
    )

    ids = store.add_documents([doc1, doc2])
    assert len(ids) == 2
    assert store.count() == 2
    assert store.count(ticker="NVDA") == 1
    assert store.count(ticker="AAPL") == 1


def test_vector_store_search_with_filter(temp_vector_store):
    """Verify semantic search and metadata filtering."""
    store = temp_vector_store
    doc = ResearchDocument(
        id="tsla-q3-2024-001",
        content="Tesla automotive gross margin excluding regulatory credits was 14.6%.",
        ticker="TSLA",
        source_type="earnings_call",
        confidence=0.92,
        verified=False
    )
    store.add_document(doc)

    # Search with matching ticker
    matches = store.search("automotive gross margin", ticker="TSLA", top_k=3)
    assert len(matches) == 1
    assert matches[0].document.ticker == "TSLA"
    assert matches[0].document.verified is False

    # Search with non-matching ticker
    empty_matches = store.search("automotive gross margin", ticker="GOOGL", top_k=3)
    assert len(empty_matches) == 0


def test_vector_store_get_and_delete(temp_vector_store):
    """Verify retrieval by ID and document deletion."""
    store = temp_vector_store
    doc = ResearchDocument(
        id="msft-risk-001",
        content="Cybersecurity risks and supply chain constraints in cloud data centers.",
        ticker="MSFT",
        source_type="10-K",
    )
    store.add_document(doc)

    retrieved = store.get_by_id("msft-risk-001")
    assert retrieved is not None
    assert retrieved.id == "msft-risk-001"
    assert retrieved.ticker == "MSFT"

    store.delete_by_id("msft-risk-001")
    assert store.get_by_id("msft-risk-001") is None
    assert store.count() == 0


def test_document_chunker_sec_filing():
    """Verify section-aware chunking for SEC filings with Item boundaries."""
    from memory.vector_store import DocumentChunker

    filing_text = """
    ITEM 1. BUSINESS
    Microsoft Corporation develops software, services, and hardware solutions globally.
    Core offerings include Windows OS, Office 365, and Azure cloud infrastructure.

    ITEM 1A. RISK FACTORS
    Competition in hyperscale cloud computing and AI infrastructure poses significant risks.
    Supply chain shortages for advanced GPUs could constrain Azure growth.
    Cybersecurity threats against enterprise tenants represent material liabilities.

    ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS
    Total revenue for FY2024 grew 16% YoY to $245 billion driven by Intelligent Cloud expansion.
    Operating income reached $109 billion with operating margin expanding to 44.6%.
    """

    chunks = DocumentChunker.chunk_sec_filing(
        text=filing_text,
        ticker="MSFT",
        filing_type="10-K",
        year=2024,
        source_url="https://sec.gov/edgar/msft-10k-2024.htm",
    )

    assert len(chunks) >= 3
    # Check that section tags are preserved
    tags = [c.metadata.get("section_tag") for c in chunks]
    assert "item1" in tags
    assert "item1a" in tags
    assert "item7" in tags

    # Verify ID format and metadata
    for c in chunks:
        assert c.ticker == "MSFT"
        assert c.source_type == "10-K"
        assert c.confidence == 0.98
        assert c.verified is True
        assert "MSFT 10-K (2024)" in c.content


def test_document_chunker_transcript_qa():
    """Verify earnings call transcript chunking with Q&A speaker pairing."""
    from memory.vector_store import DocumentChunker

    transcript_text = """
    Satya Nadella: Welcome to Microsoft's Q4 FY24 earnings call. We delivered strong results with Azure AI revenue up 29%.
    Amy Hood: Cloud gross margins remained healthy at 70%.

    Questions and Answers Session
    Keith Weiss (Morgan Stanley): Could you provide more color on Azure AI capacity constraints and CapEx expectations?
    Satya Nadella: Demand continues to be higher than our available capacity. We are investing aggressively in data centers.
    Amy Hood: We expect CapEx to increase sequentially as we build out GPU clusters.

    Brent Thill (Jefferies): How should we think about Copilot monetization across Microsoft 365 commercial seats?
    Satya Nadella: Copilot adoption is accelerating, with over 60% of Fortune 500 companies now using Copilot Studio.
    """

    chunks = DocumentChunker.chunk_earnings_transcript(
        text=transcript_text,
        ticker="MSFT",
        quarter="Q4",
        year=2024,
        source_url="https://investor.microsoft.com/q4-2024-transcript",
    )

    assert len(chunks) >= 2
    # Verify that Analyst Question and Executive Answer are paired in the chunk
    qa_chunks = [c for c in chunks if c.metadata.get("segment") in ("qa_pair", "qa_dialogue")]
    assert len(qa_chunks) >= 1
    assert any("Keith Weiss" in c.content and "Satya Nadella" in c.content for c in qa_chunks)


def test_document_chunker_news():
    """Verify news chunking with headline, publisher, and timestamp prepend."""
    from memory.vector_store import DocumentChunker

    title = "Microsoft Expands Supercomputing AI Clusters in Europe"
    text = (
        "Microsoft announced a multi-billion dollar expansion of sovereign AI data centers in the European Union.\n\n"
        "The infrastructure will provide dedicated compute capacity for enterprises and government agencies "
        "complying with stringent GDPR regulations."
    )

    chunks = DocumentChunker.chunk_news_article(
        title=title,
        text=text,
        ticker="MSFT",
        publisher="Reuters",
        date="2024-10-01",
    )

    assert len(chunks) >= 1
    assert "Headline: Microsoft Expands Supercomputing" in chunks[0].content
    assert "Publisher: Reuters" in chunks[0].content
    assert chunks[0].ticker == "MSFT"
    assert chunks[0].source_type == "news"


def test_vector_store_ingestion_pipelines(temp_vector_store):
    """Verify high-level ingestion pipelines in FinancialVectorStore."""
    store = temp_vector_store

    # Ingest filing
    filing_text = "ITEM 1. BUSINESS\nApple designs smartphones and tablets.\n\nITEM 1A. RISK FACTORS\nSupply chains in Asia."
    ids1 = store.ingest_filing(filing_text, ticker="AAPL", filing_type="10-K", year=2024)
    assert len(ids1) >= 2
    assert store.count(ticker="AAPL") >= 2

    # Ingest news
    ids2 = store.ingest_news("Apple AI Launch", "Apple announced new generative features.", ticker="AAPL", publisher="Bloomberg")
    assert len(ids2) >= 1
    assert store.count(ticker="AAPL") == len(ids1) + len(ids2)


def test_context_manager_operations():
    """Verify ContextManager token estimation, observation compaction, and progressive summarization."""
    from memory.context_manager import ContextManager, ContextBudgetConfig

    cm = ContextManager(config=ContextBudgetConfig(max_history_tokens=100, preserve_recent_steps=1))

    # Test token estimation
    assert cm.estimate_tokens("Hello financial world") > 0

    # Test observation compaction of structured JSON
    structured_data = {
        "ticker": "MSFT",
        "annual_metrics": [
            {"year": "FY24", "revenue": "$245B", "operating_margin": "44.6%"},
            {"year": "FY23", "revenue": "$211B", "operating_margin": "41.8%"},
        ]
    }
    compacted = cm.compact_observation(structured_data)
    assert "| year | revenue | operating_margin |" in compacted
    assert "$245B" in compacted

    # Test progressive summarization
    history = [
        "Research Query: Microsoft financial overview",
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

    managed_history = cm.manage_context(history, force_summary=True)
    joined_res = "\n".join(managed_history)
    assert "PROGRESSIVE SUMMARY OF EARLIER RESEARCH STEPS" in joined_res
    assert "Thought: Step 3 finalize analysis" in joined_res
    assert cm.get_metrics()["total_compressions"] >= 1


def test_episodic_memory_store_operations():
    """Verify EpisodicMemoryStore recording, error recovery, and strategy retrieval."""
    import tempfile
    from pathlib import Path
    from memory.episodic import EpisodicMemoryStore, EpisodicRecord, ErrorRecoveryPath

    with tempfile.TemporaryDirectory() as tmp_dir:
        store_path = Path(tmp_dir) / "test_episodes.json"
        store = EpisodicMemoryStore(persist_path=str(store_path))

        # Initial baseline seeds present
        assert store.count() >= 2

        # Record new episode
        rec = EpisodicRecord(
            query="Analyze NVIDIA GPU data center margins",
            query_type="earnings_analysis",
            target_ticker="NVDA",
            tool_sequence=["financial_data_api", "sec_filing_search"],
            successful_plan=["Step 1: Check gross margins", "Step 2: Verify against 10-Q"],
            reflection="Data center gross margins exceeded 75% due to Hopper demand.",
            outcome_quality=0.99
        )
        saved_id = store.record_episode(rec)
        assert saved_id.startswith("ep-")
        assert store.count() >= 3

        # Record error recovery path
        store.record_error_recovery(
            failed_tool="sec_filing_search",
            error_message="EDGAR 429 Too Many Requests",
            recovery_tool="web_search",
            recovery_action="Fallback to SEC index on investor relations",
            success=True,
            ticker="NVDA"
        )
        recovs = store.get_recovery_recommendations("sec_filing_search")
        assert len(recovs) >= 1
        assert any(r.recovery_tool == "web_search" for r in recovs)

        # Retrieve strategy
        strategies = store.retrieve_strategy("NVIDIA margin analysis", target_ticker="NVDA", top_k=1)
        assert len(strategies) >= 1
        assert strategies[0].target_ticker == "NVDA"

        formatted = store.format_strategy_for_planner(strategies)
        assert "Procedural Insights" in formatted
        assert "financial_data_api" in formatted


def test_memory_tools_integration():
    """Verify VectorDbSearchTool and VectorDbStoreTool via ToolRegistry."""
    import tempfile
    import shutil
    from memory.vector_store import FinancialVectorStore
    from tools.memory_tools import VectorDbSearchTool, VectorDbStoreTool

    tmp_dir = tempfile.mkdtemp()
    vstore = FinancialVectorStore(persist_directory=tmp_dir, collection_name="tool_test_collection")

    search_tool = VectorDbSearchTool(vector_store=vstore)
    store_tool = VectorDbStoreTool(vector_store=vstore)

    # 1. Store a document via VectorDbStoreTool
    store_res = store_tool(
        content="Alphabet Google Cloud achieved $10B quarterly revenue run rate with 11% operating margin.",
        metadata={"ticker": "GOOGL", "source_type": "earnings_call", "confidence": 0.94, "verified": True}
    )
    assert store_res.success is True
    assert store_res.data["status"] == "stored"
    assert store_res.data["ticker"] == "GOOGL"

    # 2. Search via VectorDbSearchTool
    search_res = search_tool(
        query="Google Cloud revenue run rate",
        top_k=2,
        filter={"ticker": "GOOGL"}
    )
    assert search_res.success is True
    assert len(search_res.data) >= 1
    assert search_res.data[0]["ticker"] == "GOOGL"
    assert "Google Cloud achieved $10B" in search_res.data[0]["content"]

    vstore.close()
    shutil.rmtree(tmp_dir, ignore_errors=True)

