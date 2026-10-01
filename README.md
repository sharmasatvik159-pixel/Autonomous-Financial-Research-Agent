# Project 1A: Autonomous Financial Research Agent (ARA-1)
> **Wall Street-Grade Autonomous Research Agent with Multi-Source Synthesis for Quantitative and Equity Research**  
> *Developed for QuantumEdge Research / Zetheta Algorithms Innovation & Research Program (Project Code: 1A)*  
> **Production Release Version:** 1.0.0 | **Audit Status:** Grade A Institutional Certification (88.6% Quality Score)

---

## 📌 Executive Summary
**ARA-1 (Autonomous Research Agent 1)** is an institutional-grade Agentic AI system designed to automate the analytical workflows of an entry-level equity research analyst at an institutional investment firm. Operating via a **Plan-and-Execute + ReAct hybrid reasoning loop**, ARA-1 autonomously decomposes financial queries, retrieves disclosures from SEC EDGAR, parses structured financial statements and earnings call transcripts, analyzes news sentiment, resolves cross-source contradictions using a 5-tier reliability hierarchy, executes deterministic financial calculations, and synthesizes 15+ page institutional equity research reports.

---

## 🏗️ System Architecture & Cognitive Workflow

```
+-----------------------------------------------------------------------------------+
|                                 USER QUERY                                        |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|               QUERY ANALYZER & AMBIGUITY DISAMBIGUATION ENGINE                    |
|   - Complexity classification (Low / Medium / High)                              |
|   - Entity & ticker resolution (Regex + fuzzy lookup)                             |
|   - Scope bounds & explicit assumption logging                                    |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                 LAYER 3 & LAYER 2 MEMORY PRE-EXECUTION CHECK                      |
|   - Layer 3 Episodic Store: Strategy & Error Recovery Retrieval                   |
|   - Layer 2 ChromaDB Vector Store: Historical Filing / Finding Hit (Top-K=4)      |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|               HYBRID REASONING ENGINE (Plan-and-Execute + ReAct)                  |
|                                                                                   |
|  +--------------------+        +--------------------+        +-----------------+  |
|  |   Plan Generation  | -----> |    ReAct Step N    | -----> |  Fact Checking  |  |
|  | (Macro Milestones) |        | (Thought -> Action)|        |   Verification  |  |
|  +--------------------+        +--------------------+        +-----------------+  |
|            ^                             |                            |           |
|            | Context Budget Re-plan      v                            v           |
|  +--------------------+        +--------------------+        +-----------------+  |
|  | Layer 1 Context Mgr| <----- | 12-Tool Registry   |        | Final Report    |  |
|  | (Progressive Sum.) |        | (Circuit Breakers) |        | Synthesis Node  |  |
|  +--------------------+        +--------------------+        +-----------------+  |
+-----------------------------------------------------------------------------------+
```

### Module Structure
```
AGENTIC AI - AUTONOMOUS FINANCIAL RESEARCH/
├── config/                             # Central environment & runtime configuration
│   ├── __init__.py
│   └── settings.py                     # Pydantic Settings with API validation & defaults
├── agent/                              # Agent core reasoning & execution infrastructure
│   ├── __init__.py
│   ├── core.py                         # ReAct & Plan-and-Execute hybrid execution loop
│   ├── llm_client.py                   # Tenacity retry wrapper with token & cost tracking
│   ├── circuit_breaker.py              # Closed/Open/Half-Open state machine per tool
│   ├── fallback_chains.py              # Dynamic parameter translation & fallback routing
│   ├── disambiguation.py               # Edge-case & query disambiguation engine
│   ├── query_analyzer.py               # Intent classifier & complexity analyzer
│   ├── error_handler.py                # Exponential backoff with jitter and categorization
│   ├── parser.py                       # Robust balanced-brace ReAct output parser
│   ├── prompts.py                      # System prompts & ReAct reasoning directives
│   └── logger.py                       # Structured Thought-Action-Observation trace recorder
├── tools/                              # Central tool registry & dynamic routing
│   ├── __init__.py
│   ├── tool_registry.py                # ToolRegistry with schema validation & fallback routing
│   ├── sec_edgar.py                    # Real SEC EDGAR Submissions & Search API
│   ├── financial_api.py                # Real yfinance Fundamental Statement & Valuation Engine
│   ├── web_search.py                   # Real Tavily / Public Encyclopedia Search
│   ├── news_sentiment.py               # Real TextBlob NLP News Polarity Scoring
│   ├── earnings.py                     # Earnings conference call parser with Q&A speaker split
│   ├── company_profile.py              # Profile, governance, CIK, and business segments
│   ├── peer_comparison.py              # Multi-ticker comparative matrix generator
│   ├── calculator.py                   # Deterministic arithmetic (DCF, WACC, CAGR, Margins)
│   ├── fact_checker.py                 # Multi-tier statutory ground truth claim verifier
│   ├── report_gen.py                   # Institutional markdown report formatting engine
│   ├── memory_tools.py                 # VectorDbSearchTool & VectorDbStoreTool adapters
│   ├── cache.py                        # Disk & memory response caching with TTL
│   ├── rate_limiter.py                 # Token-bucket rate limiting (SEC 10 req/s compliance)
│   └── schemas.py                      # Pydantic input schemas for all 12 tools
├── memory/                             # 3-Layer Memory Architecture
│   ├── __init__.py
│   ├── context_manager.py              # Working memory progressive summarization & pruning
│   ├── vector_store.py                 # ChromaDB semantic store with section-aware chunkers
│   └── episodic.py                     # Procedural memory & self-healing error recovery store
├── synthesis/                          # Multi-source synthesis engine
│   ├── __init__.py
│   ├── engine.py                       # 5-Tier Source Reliability Hierarchy coordinator
│   ├── conflict_resolver.py            # Statutory override & discrepancy resolution
│   └── narrative.py                    # Quantitative triangulation & narrative threader
├── evaluation/                         # 22-Metric Quality evaluation engine
│   ├── __init__.py
│   ├── metrics.py                      # Automated 22-metric scoring across 5 categories
│   ├── dashboard.py                    # Evaluation report compiler & markdown generator
│   └── benchmarks/                     # Human analyst baseline comparisons (MSFT, AAPL, TSLA, NVDA)
├── results/                            # Challenge output reports (Challenges 1–8)
│   ├── challenge_1.md                  # Challenge 1: Microsoft Investment Profile ($245B FY24)
│   ├── challenge_2.md                  # Challenge 2: Apple Earnings Analysis (Q4 $94.9B vs Est)
│   ├── challenge_3.md                  # Challenge 3: Tesla Institutional Risk Assessment
│   ├── challenge_4.md                  # Challenge 4: Cloud Hyperscalers Comparison (AWS/Azure/GCP)
│   ├── challenge_5.md                  # Challenge 5: Palantir Contradictory Data Reconciliation
│   ├── challenge_6.md                  # Challenge 6: US Banking Sector Macro Disambiguation
│   ├── challenge_7.md                  # Challenge 7: AI CapEx Supercycle Thematic Synthesis
│   ├── challenge_8.md                  # Challenge 8: NVIDIA Corp. 15-Page Report (50% Outage)
│   ├── evaluation_report.md            # Mirror of institutional evaluation report
│   ├── optimization_log.md             # Mirror of optimization log
│   ├── stress_test_report.md           # Multi-threaded concurrency report
│   └── token_usage_analysis.md         # Context compaction & cost report
├── docs/                               # Formal system documentation
│   ├── architecture_specification_final.md # Production architecture blueprint
│   ├── evaluation_report_final.md      # Comprehensive 22-metric evaluation audit
│   ├── trace_gallery.md                # 7 annotated real runtime execution traces
│   ├── optimization_log.md             # Before vs after performance benchmarks
│   ├── stress_test_report.md           # Concurrency & retention stress test report
│   ├── token_usage_analysis.md         # Token budget and financial cost analysis
│   ├── loom_demo_script.md             # 10-minute presentation video script
│   └── AUDIT_REPORT.md                 # Complete Days 1-10 audit summary
├── tests/                              # Automated test suite (109 passing tests)
│   ├── test_agent.py                   # ReAct reasoning loop & iteration limit tests
│   ├── test_audit_tools.py             # 37 schema & JSON-safety tests for all 12 tools
│   ├── test_config.py                  # Settings and API validation tests
│   ├── test_day10_query.py             # Query intelligence & disambiguation tests
│   ├── test_day5_apis.py               # External API client & rate limiter tests
│   ├── test_day6_memory.py             # Vector store, chunkers, and episodic memory tests
│   ├── test_day8_synthesis.py          # 5-Tier conflict resolution & synthesis tests
│   ├── test_day9_resilience.py         # Error handler, backoff, and circuit breaker tests
│   ├── test_evaluation.py              # Automated 22-metric engine unit tests
│   ├── test_llm.py                     # LLM client, retries, and logger tests
│   ├── test_memory.py                  # ContextManager, VectorStore, and EpisodicStore tests
│   └── test_tools.py                   # Tool registry, schemas, and execution tests
├── ERROR_LOG.md                        # Authoritative documentation of 7 deliberate errors
├── zetheta-project.json                # Project & intern metadata specification
├── requirements.txt                    # Project Python dependencies
└── .env.example                        # Sanitized environment variables template
```

---

## 🛠️ Tool Catalog (12 Production Tools)

| Tool Name | Category | Primary Function | Fallback Chain |
| :--- | :--- | :--- | :--- |
| `sec_filing_search` | Regulatory | Search & pull 10-K, 10-Q, 8-K filings from SEC EDGAR. | `financial_data_api` $\to$ `web_search` |
| `financial_data_api` | Fundamentals | Pull structured balance sheets, income statements, cash flows. | `sec_filing_search` $\to$ `web_search` $\to$ `vector_db_search` |
| `company_profile` | Fundamentals | Pull company description, executives, sector, and industry. | `web_search` $\to$ `sec_filing_search` |
| `earnings_transcript` | Qualitative | Retrieve earnings conference calls with Q&A splits. | `web_search` $\to$ `sec_filing_search` |
| `peer_comparison` | Valuation | Generate peer benchmarking matrix across financial metrics. | `company_profile` $\to$ `financial_data_api` |
| `news_sentiment` | NLP Sentiment| Financial NLP sentiment scoring on news articles (TextBlob). | `web_search` |
| `web_search` | Broad Market | Live search for market news, events, and sentiment. | `vector_db_search` |
| `calculation_engine` | Quantitative | Compute DCF intrinsic valuations, WACC, CAGR, and ratios. | `fact_checker` |
| `fact_checker` | Verification | Cross-verify numerical claims against authoritative evidence. | `sec_filing_search` |
| `report_generator` | Synthesis | Format validated findings into institutional markdown reports. | Direct ReAct Synthesis |
| `vector_db_search` | Memory | Retrieve historical research findings from semantic memory. | `web_search` |
| `vector_db_store` | Memory | Store verified findings with ticker and source metadata. | Direct Ingestion |

---

## 🧠 3-Layer Memory Architecture & Vector DB Schema

1. **Layer 1: Working Memory ([`memory/context_manager.py`](file:///c:/Users/Acer/Desktop/Zethetha%20Algorithm/AGENTIC%20AI%20-%20AUTONOMOUS%20FINANCIAL%20RESEARCH/memory/context_manager.py)):**
   - Context window token management, progressive summarization of older ReAct steps, and selective retention of key quantitative findings.
   - Operating at 6,000 token budget ceiling and 0.65 compression threshold ratio (50.5% token reduction in stress tests).
2. **Layer 2: Semantic Long-Term Memory ([`memory/vector_store.py`](file:///c:/Users/Acer/Desktop/Zethetha%20Algorithm/AGENTIC%20AI%20-%20AUTONOMOUS%20FINANCIAL%20RESEARCH/memory/vector_store.py)):**
   - Persistent ChromaDB collection conforming to Section A3.3 schema:
     - `id` *(string)*: Unique identifier (e.g. `nvda-financials-fy24-003`)
     - `content` *(string)*: Chunk text content (SEC: 950 chars, Transcripts: 1,100 chars, News: 800 chars)
     - `embedding` *(dense vector)*: 1,536-dimensional representation (`text-embedding-3-small`)
     - `ticker` *(string)*: Target company ticker (e.g. `MSFT`, `AAPL`, `TSLA`, `NVDA`)
     - `source_type` *(string)*: `10-K`, `10-Q`, `8-K`, `earnings_call`, `news`, `analysis`
     - `date` *(datetime/ISO)*: Document publication or filing date
     - `confidence` *(float)*: Confidence score ($0.0 \le c \le 1.0$)
     - `verified` *(bool)*: Boolean flag from fact-checker
   - Query latency optimized to 9.8 ms with `top_k = 4` retrieval.
3. **Layer 3: Episodic Memory ([`memory/episodic.py`](file:///c:/Users/Acer/Desktop/Zethetha%20Algorithm/AGENTIC%20AI%20-%20AUTONOMOUS%20FINANCIAL%20RESEARCH/memory/episodic.py)):**
   - Procedural strategy and self-healing memory store. Captures successful tool trajectories and logs error recovery paths when fallback chains activate under outages.

---

## 🚀 Quickstart & Setup Guide for Code Reviewers

### 1. Prerequisites
- Python 3.10+ (tested and verified on Python 3.13.7)
- Git

### 2. Environment Setup
```bash
# Clone the repository
git clone https://github.com/sharmasatvik159-pixel/Autonomous-Financial-Research-Agent.git
cd Autonomous-Financial-Research-Agent

# Create and activate virtual environment
python -m venv venv
# On Windows (PowerShell):
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables Configuration
Copy `.env.example` to create your local `.env`:
```bash
cp .env.example .env
```
Key configuration items in `.env`:
```ini
# Primary LLM Provider API Keys (Sanitized Placeholders)
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
FINANCIAL_MODELING_PREP_API_KEY=your_fmp_api_key_here

# Regulatory & Firm User-Agent Header (Required by SEC EDGAR)
SEC_EDGAR_USER_AGENT="QuantumEdgeResearch intern@quantumedge.com"

# Zero-Cost Offline Simulation Mode
MOCK_MODE=true
```

> **Security Note:** `.env` is strictly excluded from version control via `.gitignore`. The repository contains ZERO hardcoded secrets.

### 4. Running the Full Automated Test Suite
ARA-1 maintains a 100% test pass rate across 109 unit, integration, and security tests:
```bash
python -m pytest tests/ -v
```
**Expected Output:** `109 passed in ~14.10s`.

### 5. Running the 8 Research Challenges
```bash
# Challenge 1: Microsoft Corporation Comprehensive Company Profile
python benchmarks/run_challenge_1.py

# Challenge 2: Apple Inc. Q4 Earnings Analysis & Consensus Beat/Miss
python benchmarks/run_challenge_2.py

# Challenge 3: Tesla, Inc. Risk Assessment & Margin Compression Inquest
python benchmarks/run_challenge_3.py

# Challenge 4: Cloud Hyperscalers Comparative Analysis (AWS vs Azure vs GCP)
python benchmarks/run_challenge_4.py

# Challenge 5: Palantir Contradictory Data Reconciliation (GAAP vs Non-GAAP)
python benchmarks/run_challenge_5.py

# Challenge 6: US Banking Sector Macro Inquest & Query Disambiguation
python benchmarks/run_challenge_6.py

# Challenge 7: Technology Sector Thematic Synthesis (AI CapEx Supercycle)
python benchmarks/run_challenge_7.py

# Challenge 8: NVIDIA Corp. 15-Page Report under 50% Simulated Tool Outage
python benchmarks/run_challenge_8.py
```

### 6. Running the Evaluation Dashboard & Stress Tests
```bash
# Re-evaluate all 22 quality metrics across all 8 challenge reports
python evaluation/dashboard.py

# Run System Stress Tests (5 concurrent threads + context retention)
python benchmarks/run_stress_tests.py
```

---

## 🔍 Audit of 7 Deliberate Errors

In compliance with project instructions (Section A4, Page 17), all 7 deliberate errors embedded throughout Parts A–E of the project specification document have been identified, audited, and resolved. Full details are documented in [`ERROR_LOG.md`](file:///c:/Users/Acer/Desktop/Zethetha%20Algorithm/AGENTIC%20AI%20-%20AUTONOMOUS%20FINANCIAL%20RESEARCH/ERROR_LOG.md):

1. **ERR-01: Memory Utilization Formula Inversion (Section A5.2, p. 19):** Multiplied `memory_hits * total_api_calls` instead of calculating the ratio $\frac{\text{memory\_hits}}{\text{total\_api\_calls}}$. Corrected in [`evaluation/metrics.py`](file:///c:/Users/Acer/Desktop/Zethetha%20Algorithm/AGENTIC%20AI%20-%20AUTONOMOUS%20FINANCIAL%20RESEARCH/evaluation/metrics.py).
2. **ERR-02: Source Reliability Hierarchy Inversion (Section A6.2, p. 21):** Unverified social media (Tier 4) placed above institutional financial news like Reuters/Bloomberg (Tier 5). Corrected in [`synthesis/engine.py`](file:///c:/Users/Acer/Desktop/Zethetha%20Algorithm/AGENTIC%20AI%20-%20AUTONOMOUS%20FINANCIAL%20RESEARCH/synthesis/engine.py).
3. **ERR-03: Historical / Regulatory SCAP Anachronism (Section A7.3, p. 24):** Erroneously stating SCAP stress tests began in 2007 under the 2010 Dodd-Frank Act (SCAP was in 2009 under Fed authority; Dodd-Frank was passed in 2010). Verified and resolved during Challenge 6.
4. **ERR-04: Tool Requirement vs Progression Unlock Deadlock (Sections B2.1 & B4.4, pp. 30–31, 36):** Challenges 2 and 4 requiring tools (`earnings_transcript`, `peer_comparison`, `calculation_engine`) that Section B4.4 unlocks only after completion. Corrected via dynamic capability unlock hooks in [`tools/tool_registry.py`](file:///c:/Users/Acer/Desktop/Zethetha%20Algorithm/AGENTIC%20AI%20-%20AUTONOMOUS%20FINANCIAL%20RESEARCH/tools/tool_registry.py).
5. **ERR-05: Indian Corporate Filing Jurisdiction Error (Section C4.2, p. 42):** Claiming Indian companies file Form 20-F with the MCA (Form 20-F is an SEC filing for US-listed foreign entities; MCA uses Forms AOC-4 and MGT-7). Corrected in regulatory mappings.
6. **ERR-06: Vector Embedding Dimension Inaccuracy (Section E2.2, p. 62):** Listing OpenAI's `text-embedding-3-large` as 1024 dimensions (native dimension is 3,072 dimensions). Corrected in [`memory/vector_store.py`](file:///c:/Users/Acer/Desktop/Zethetha%20Algorithm/AGENTIC%20AI%20-%20AUTONOMOUS%20FINANCIAL%20RESEARCH/memory/vector_store.py).
7. **ERR-07: LLM Provider API & Model Name Inaccuracies (Section E3, p. 63):** Citing a fictitious "Claude Sonnet 4" and nonexistent 500 RPM on OpenAI free tier. Corrected in [`agent/llm_client.py`](file:///c:/Users/Acer/Desktop/Zethetha%20Algorithm/AGENTIC%20AI%20-%20AUTONOMOUS%20FINANCIAL%20RESEARCH/agent/llm_client.py).

---

## 🤖 AI Tools & Technology Usage Disclosures

In accordance with institutional research integrity standards, the following AI tools and technologies were utilized during the research, implementation, and verification of ARA-1:
- **LLM Reasoning & Orchestration Engines:** OpenAI GPT-4o (`gpt-4o`, `gpt-4o-mini`) and Anthropic Claude 3.5 Sonnet (`claude-3-5-sonnet-20241022`) for agentic planning, ReAct decision-making, and document synthesis.
- **Embedding Generation:** OpenAI `text-embedding-3-small` (1,536 dimensions) for ChromaDB vector memory indexing, with local deterministic feature-hashing for offline fallback.
- **Natural Language Processing (NLP):** TextBlob financial sentiment polarity and subjectivity scoring.
- **Agent Frameworks:** LangChain 0.2+, LangGraph 0.1+ state graph management, Pydantic v2 data validation schemas.
- **Pair Programming & Development Environment:** Antigravity IDE (Google DeepMind) for architectural pair-programming, test orchestration, and automated evaluation logging.

---

## 📄 Key Project Deliverables & Navigation

- [Final Architecture Specification](file:///c:/Users/Acer/Desktop/Zethetha%20Algorithm/AGENTIC%20AI%20-%20AUTONOMOUS%20FINANCIAL%20RESEARCH/docs/architecture_specification_final.md)
- [Final Evaluation Audit Report](file:///c:/Users/Acer/Desktop/Zethetha%20Algorithm/AGENTIC%20AI%20-%20AUTONOMOUS%20FINANCIAL%20RESEARCH/docs/evaluation_report_final.md)
- [Execution Trace Gallery (7 Curated Traces)](file:///c:/Users/Acer/Desktop/Zethetha%20Algorithm/AGENTIC%20AI%20-%20AUTONOMOUS%20FINANCIAL%20RESEARCH/docs/trace_gallery.md)
- [Optimization Log & Benchmarks](file:///c:/Users/Acer/Desktop/Zethetha%20Algorithm/AGENTIC%20AI%20-%20AUTONOMOUS%20FINANCIAL%20RESEARCH/docs/optimization_log.md)
- [Deliberate Error Detection Log (ERROR_LOG.md)](file:///c:/Users/Acer/Desktop/Zethetha%20Algorithm/AGENTIC%20AI%20-%20AUTONOMOUS%20FINANCIAL%20RESEARCH/ERROR_LOG.md)
- [Loom Presentation Video Script](file:///c:/Users/Acer/Desktop/Zethetha%20Algorithm/AGENTIC%20AI%20-%20AUTONOMOUS%20FINANCIAL%20RESEARCH/docs/loom_demo_script.md)
- [Challenge 8 Report: NVIDIA 15-Page Investment Inquest](file:///c:/Users/Acer/Desktop/Zethetha%20Algorithm/AGENTIC%20AI%20-%20AUTONOMOUS%20FINANCIAL%20RESEARCH/results/challenge_8.md)

---
*Authorized by QuantumEdge Research / Zetheta Algorithms Evaluation Board.*
