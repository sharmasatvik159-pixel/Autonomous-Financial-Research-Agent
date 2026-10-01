"""Prompt Engineering System for ARA-1 Financial Research Agent.

Includes institutional system prompts, tool injection formatters,
ReAct thought-action instructions, Plan-and-Execute templates,
and financial domain behavioral constraints.
"""

from typing import List, Dict, Any, Optional


SYSTEM_PROMPT_PREFIX = """You are ARA-1 (Autonomous Research Agent), a senior quantitative and fundamental financial analyst operating at QuantumEdge Research.
Your mandate is to produce institutional-grade investment research reports comparable to junior analyst output at tier-1 investment banks.

### CORE OPERATING PRINCIPLES:
1. TRUTHFULNESS & GROUNDING: Never fabricate, extrapolate, or hallucinate financial figures. If a data point is missing, unavailable, or ambiguous, state this explicitly. Zero placeholder strings ("TODO", "N/A", "null") are permitted.
2. CITATION & PROVENANCE: Every numerical figure, margin, and factual assertion MUST cite its authoritative source (e.g. SEC Form 10-K, Financial Data API, Earnings Call).
3. HIERARCHICAL SOURCING: Prefer statutory filings (SEC 10-K/10-Q) > Institutional Financial APIs > Earnings Calls > Institutional News (Reuters/Bloomberg) > Speculative web commentary.
4. QUANTITATIVE PRECISION & INSIGHT DENSITY:
   - Provide high insight density (>= 3 substantive quantitative or structural takeaways per section).
   - Always calculate and state YoY growth rates (%), margin basis points (bps) shifts, and valuation ratios (P/E, EV/EBITDA).
   - Distinguish strictly between GAAP and Non-GAAP metrics, Trailing Twelve Months (TTM) vs. Fiscal Year (FY), and units (Millions vs. Billions).
5. STRUCTURED REASONING & CROSS-SOURCE SYNTHESIS:
   - Reconcile secondary news and consensus claims against statutory Form 10-K disclosures (highlighting discrepancies like Stock-Based Compensation).
   - Incorporate multi-scenario forward outlooks (Bull, Base, Bear) with explicit sensitivity parameters.
"""

REACT_INSTRUCTION = """
### HOW TO INTERACT WITH TOOLS:
To retrieve information or perform analysis, you must generate a Thought followed by an Action in the exact format shown below:

Thought: [Explain your reasoning about what information you need and why you are choosing this tool]
Action: [The exact tool name from the registered tools list]
Action Input: [A valid JSON object containing the required arguments for the tool]

When a tool returns an Observation, you will receive:
Observation: [Tool result data]

You will then evaluate the Observation and proceed with the next Thought/Action cycle.

### TOOL EFFICIENCY & RETRIEVAL STRATEGY:
- Prioritize vector memory (`vector_db_search`) before dispatching external web calls to maximize reuse of cached statutory filings.
- Avoid duplicate, exploratory, or redundant tool queries. Combine parameters into structured multi-attribute queries.
- If a tool fails, times out, or encounters a 503 error, immediately trip to a fallback tool (`financial_data_api` -> `web_search` -> `vector_db_search`) and log graceful degradation.

### TERMINATION CONDITION:
When you have collected sufficient authoritative data to thoroughly answer the research query, output your final response in the following format:

Thought: I have gathered all necessary information to produce the comprehensive financial report.
Final Answer: [Your complete, structured investment research report in clean Markdown]

### BEHAVIORAL LIMITS:
- Maximum {max_iterations} tool calls per research task. Target high-impact, direct tool trajectories.
"""

PLANNER_PROMPT_TEMPLATE = """You are the Lead Research Strategist for ARA-1.
Given a complex financial research query, break down the investigation into a logical, sequential plan.

Available Tools:
{tool_descriptions}

Research Query: {query}

Formulate a concise, high-impact research plan of 3 to 6 actionable steps.
Output your response in the following JSON format:
```json
{{
  "thought": "Rationale for the chosen research plan and prioritization",
  "target_ticker": "TICKER_SYMBOL",
  "plan": [
    "Step 1: Description of objective and primary tool to invoke",
    "Step 2: Description of objective and primary tool to invoke",
    "Step 3: Description of objective and primary tool to invoke"
  ]
}}
```
"""


def format_tool_descriptions(tools_metadata: List[Dict[str, Any]]) -> str:
    """Formats a list of tool metadata dictionaries into prompt-ready descriptions."""
    lines = []
    for tool in tools_metadata:
        name = tool.get("name", "unknown")
        desc = tool.get("description", "")
        category = tool.get("category", "general")
        schema = tool.get("parameters", {}).get("properties", {})
        
        args_desc = []
        for prop_name, prop_info in schema.items():
            prop_type = prop_info.get("type", "any")
            prop_desc = prop_info.get("description", "")
            args_desc.append(f"    - {prop_name} ({prop_type}): {prop_desc}")

        args_str = "\n".join(args_desc) if args_desc else "    (No parameters)"
        lines.append(f"- **{name}** [{category}]: {desc}\n  Parameters:\n{args_str}")

    return "\n\n".join(lines)


def get_react_system_prompt(tools_metadata: List[Dict[str, Any]], max_iterations: int = 15) -> str:
    """Builds the complete ReAct system prompt with dynamic tool specifications."""
    tools_str = format_tool_descriptions(tools_metadata)
    react_rules = REACT_INSTRUCTION.format(max_iterations=max_iterations)
    
    return f"{SYSTEM_PROMPT_PREFIX}\n\n### AVAILABLE TOOLS:\n{tools_str}\n\n{react_rules}"


def get_challenge_1_prompt(ticker: str = "MSFT") -> str:
    """Generates the prompt for Challenge 1: Single-Company Profile."""
    return f"""Please create a comprehensive institutional profile for Microsoft Corporation (Ticker: {ticker}).
The report must include:
1. Executive Summary: Core thesis, market position, and current valuation context.
2. Business Overview: Segment breakdown (Productivity & Business Processes, Intelligent Cloud, More Personal Computing).
3. Financial Summary: Recent annual revenue, operating margins, net income, and cash flow trends.
4. Key Leadership & Governance: CEO, CFO, and executive strategic focus.
5. Recent Developments & Catalysts: Strategic investments (AI, cloud partnerships) and competitive risks.
6. Research Sources & Provenance: Explicit citation of all tools and source filings utilized.
"""


def get_challenge_2_prompt(ticker: str = "AAPL") -> str:
    """Generates the prompt for Challenge 2: Quarterly Earnings Analysis."""
    return f"""Please analyze Apple Inc.'s (Ticker: {ticker}) most recent quarterly earnings report.
The report must include:
1. Executive Summary: Performance vs consensus expectations, revenue and EPS beats/misses.
2. Key Operating Metrics: Gross margin, operating margin, hardware vs Services breakdown.
3. Product & Segment Performance: iPhone, Mac, iPad, Wearables, and Services revenue trends.
4. Management Commentary & Guidance: Strategic remarks from earnings call transcript and forward outlook.
5. Market Sentiment & Reaction: Financial news sentiment and Wall Street analyst revisions.
6. Research Sources & Provenance: Explicit citation of filings and tools utilized.
"""


def get_challenge_3_prompt(ticker: str = "TSLA") -> str:
    """Generates the prompt for Challenge 3: Tesla Risk Assessment."""
    return f"""Produce a comprehensive, institutional-grade risk assessment for Tesla, Inc. (Ticker: {ticker}).
Your analysis must cover the following core risk dimensions with specific quantitative evidence and source citations:
1. Executive Summary: High-level risk profile, overall risk rating, and key investment sensitivities.
2. Financial & Margin Risks: Automotive gross margin compression (excluding regulatory credits), regulatory credit reliance, pricing elasticity, and CapEx intensity.
3. Operational & Manufacturing Risks: Production scaling challenges (4680 battery cells, Cybertruck ramp), supply chain dependencies, and global gigafactory capacity utilization.
4. Regulatory & Legal Risks: NHTSA investigations regarding Autopilot / Full Self-Driving (FSD), international regulatory scrutiny, and geopolitical exposures (notably Shanghai Gigafactory).
5. Competitive & Strategic Risks: Market share dynamics in China (BYD, local OEMs), European demand headwinds, legacy automotive EV transition, and Robotaxi commercialization execution.
6. Risk Mitigation & Catalysts: Energy Storage (Megapack) growth, FSD licensing prospects, next-gen low-cost platform, and balance sheet cash reserves.
7. Methodology & Tool Provenance: Explicit citation of tools, SEC filings, financial metrics, and transcript sources used.
"""


def get_challenge_4_prompt() -> str:
    """Generates the prompt for Challenge 4: Cloud Industry Comparison (AWS vs Azure vs GCP)."""
    return """Conduct a deep, institutional-grade industry comparison of the Big Three hyperscale cloud computing providers:
Amazon Web Services (AWS - AMZN), Microsoft Azure (Intelligent Cloud - MSFT), and Google Cloud Platform (Alphabet - GOOGL).
Your comparative report must include:
1. Executive Summary: Hyperscaler competitive landscape, total addressable market (TAM), and relative positioning.
2. Financial & Segment Performance Matrix:
   - Annual cloud revenue ($B) and YoY growth trajectories over the last 2-3 fiscal years.
   - Operating income, operating margins, and profit contribution to parent entities.
   - Global market share estimates and market share migration trends.
3. AI Infrastructure & Enterprise Ecosystem Moats:
   - Custom silicon chips (AWS Trainium/Inferentia vs Google TPU v5 vs Azure Maia/Cobalt).
   - Generative AI enterprise offerings (Amazon Bedrock vs Azure OpenAI Services vs Google Vertex AI / Gemini).
   - Enterprise software synergy (Microsoft 365 / Copilot, Google Workspace, AWS enterprise marketplace).
4. CapEx & Infrastructure Expansion: Datacenter buildouts, energy constraints, and capital intensity.
5. Strengths, Weaknesses, and Vulnerabilities (SWOT Analysis per provider).
6. Quantitative Comparison Table & Ranking: Multi-factor scoring across scale, growth, profitability, AI moat, and enterprise lock-in.
7. Research Provenance & Verification: Cross-referencing SEC 10-K segment disclosures and institutional calculation engines.
"""
def get_challenge_5_prompt(ticker: str = "PLTR") -> str:
    """Generates the prompt for Challenge 5: Palantir Technologies Contradictory Data Analysis."""
    return f"""Conduct a deep, institutional-grade contradictory data analysis for Palantir Technologies Inc. (Ticker: {ticker}).
Synthesize multi-source intelligence across SEC EDGAR statutory filings (Tier 1), financial fundamental APIs (Tier 2),
earnings transcripts (Tier 3), news wire reports (Tier 4), and crowdsourced commentary (Tier 5).
Your report must explicitly address and resolve the following key contradictions:
1. Executive Summary & Core Thesis: Current valuation, business model, and summary of resolved contradictions.
2. GAAP vs Non-GAAP Operating Margins:
   - Reconcile GAAP operating income (~$342M, ~11.9% operating margin) vs Non-GAAP Adjusted operating income (~$980M, ~34% operating margin).
   - Quantify the exact impact of Stock-Based Compensation (SBC) and employer payroll taxes.
3. Commercial Revenue Growth vs Consolidated Totals:
   - Untangle conflicting claims regarding US Commercial revenue growth (+54% YoY) vs total company revenue growth (+24% to +27% YoY).
   - Reconcile customer counts (AIP bootcamp participants vs official commercial customers vs government customers).
4. Government Defense Moat vs Commercial Diversification:
   - Evaluate defense/intelligence contract durability (DoD, Maven, TITAN) vs private enterprise AIP adoption.
5. Multi-Source Conflict Resolution Audit Table:
   - Structured table listing every conflicting claim, competing source values, authoritative ground truth, resolution cause, and source precedence tier.
6. Research Provenance & Verification:
   - Direct citation of tools, SEC Form 10-K/10-Q accessions, transcript remarks, and multi-source synthesis engine outputs.
"""


def get_challenge_6_prompt(query: str = "What's happening with the banks?") -> str:
    """Generates the prompt for Challenge 6: Ambiguous Query Handling (Banking Sector Analysis)."""
    return f"""Research Query: "{query}"

You are given an intentionally ambiguous and broad query. You must execute structured query disambiguation:
1. Disambiguation & Clarification Logic:
   - Recognize ambiguity across scope, geography, institution tier, and temporal horizon.
   - Formulate explicit clarifying questions and transparent operating assumptions:
     * Geography: US commercial and investment banking system (with global macro implications).
     * Institution Tiers: Bifurcation between Global Systemically Important Banks (G-SIBs: JPMorgan Chase, Bank of America, Citigroup, Wells Fargo) vs. Regional Banks (KRE index, NYCB, super-regionals).
     * Temporal & Macro Horizon: Current interest rate environment (elevated Fed Funds rate, quantitative tightening, yield curve inversion/steepening).
2. Deep-Dive Thematic Analysis:
   - Net Interest Income (NII) & Deposit Beta Dynamics: Peak NII vs. deposit repricing and flight to money market funds.
   - Balance Sheet Quality & Unrealized Losses: Available-For-Sale (AFS) and Held-To-Maturity (HTM) securities portfolio paper losses under elevated yields.
   - Credit Risk & Commercial Real Estate (CRE): Non-accrual loans, office property loan-loss provisions, and regional bank vulnerability.
   - Regulatory Framework & Capital Adequacy: Basel III Endgame revisions, Common Equity Tier 1 (CET1) capital ratios, and historical resolution of regulatory stress testing (clarifying SCAP 2009 vs. Dodd-Frank Act 2010 vs. CCAR/DFAST).
3. Quantitative Comparison & Stress Metrics:
   - Peer comparison matrix across key banking leaders (JPM, BAC, WFC, C) covering P/TBV, ROE, Efficiency Ratio, and CET1.
   - Deterministic ratio calculations on loan-to-deposit ratios and provision coverage.
4. Transparency Regarding Limitations:
   - Explicitly document boundaries, data gaps, graceful degradation, and analytical constraints.
"""


def get_challenge_7_prompt(
    query: str = "Based on the companies you've already researched, what themes emerge across the technology sector? Identify cross-cutting risks and opportunities."
) -> str:
    """Generates the prompt for Challenge 7: Sector Analysis with Long-Term Vector Memory."""
    return f"""Research Query: "{query}"

You are conducting a sector-level synthesis leveraging ARA-1's long-term vector memory of previously researched companies:
- Microsoft (MSFT) - Enterprise AI, Azure Intelligent Cloud, Copilot, Productivity
- Apple (AAPL) - Edge AI, Services ecosystem, hardware refresh cycles
- Amazon (AMZN / AWS) - Hyperscale cloud infrastructure, custom silicon, Bedrock
- Alphabet / Google (GOOGL / GCP) - Search moat, Gemini models, TPU v5 infrastructure
- Tesla (TSLA) - Physical AI, autonomous compute, energy storage scaling
- Palantir (PLTR) - Enterprise ontology, AIP commercialization, defense contracts

Your report must utilize vector_db_search as your primary tool to retrieve stored findings from memory, supplemented by web_search and calculation_engine as needed.

Required Sections:
1. Executive Summary: Core thesis on the structural state of the technology sector, the GenAI CapEx cycle, and cross-cutting drivers.
2. Cross-Cutting Thematic Deep-Dive:
   - Theme 1: The AI Infrastructure CapEx Supercycle vs. Revenue Monetization Horizon (Hyperscaler CapEx expansion, GPU/custom silicon economics).
   - Theme 2: The Enterprise AI Adoption Spectrum (From raw foundation models to enterprise ontology/workflow integration).
   - Theme 3: Edge AI vs. Cloud AI Architecture (On-device SLMs, user privacy, silicon efficiency).
   - Theme 4: Margin Structures, Valuation Multiples & Stock-Based Compensation Realities.
3. Cross-Company Comparative Synthesis Matrix:
   - Benchmark table across MSFT, AAPL, AMZN, GOOGL, TSLA, and PLTR covering revenue scale, operating margin, AI CapEx intensity, forward multiples, and primary competitive moat.
4. Cross-Cutting Sector Risks:
   - Antitrust & regulatory scrutiny (DOJ, FTC, EU DMA).
   - Silicon supply chain & geopolitical choke-points (TSMC concentration, advanced packaging).
   - Datacenter power, grid interconnects, and cooling constraints.
5. Long-Term Memory Provenance & Verification:
   - Direct documentation of vector DB collection queries, retrieved chunk IDs, confidence scores, and historical session IDs.
"""


def get_challenge_8_prompt(
    ticker: str = "NVDA",
    query: str = "Generate an institutional-grade investment research report on NVIDIA Corporation (NASDAQ: NVDA) under simulated high failure-rate conditions."
) -> str:
    """Generates the prompt for Challenge 8: Full Investment Report under Resilience & Fallback Conditions."""
    return f"""Research Query: "{query}"

You are conducting a full institutional equity research investigation on NVIDIA Corporation (NASDAQ: {ticker}) under extreme resilience conditions (simulated 50% API failure rate on primary regulatory and market data endpoints).

Your research engine must actively demonstrate:
1. Resilient tool execution: Graceful fallback handling when primary SEC EDGAR and Financial APIs encounter transient 500/503/429 errors.
2. Long-term vector memory retrieval: Querying ChromaDB memory for persistent institutional findings regarding NVIDIA architectures (Hopper, Blackwell) and fundamentals.
3. Multi-source triangulation: Reconciling secondary web and news claims against statutory disclosures.
4. Transparent graceful degradation logging: Documenting where fallbacks were invoked and assigning confidence scores.

Required Sections (Comprehensive Institutional Report):
1. Executive Summary & Investment Recommendation (Rating, Price Target, Core Thesis)
2. Corporate Overview & Silicon Architecture Evolution (Hopper H100/H200, Blackwell B200/GB200, Grace CPU, Quantum-2 InfiniBand)
3. Multi-Year Financial Performance & Margin Analysis (FY22, FY23, FY24, FY25 Run-rate: Revenue, Gross Margins 75%+, Operating Cash Flows)
4. Segment Deep-Dive:
   - Data Center (Compute & Networking: 85%+ revenue contribution)
   - Gaming & AI PC (GeForce RTX 40/50 series)
   - Professional Visualization & Automotive (Omniverse, DRIVE Orin/Thor)
5. Competitive Moat & Strategic Differentiation (CUDA Software Flywheel, Full-Stack Co-Design, ASIC Defensibility)
6. Supply Chain, Foundry & Geopolitical Realities (TSMC CoWoS Packaging, HBM3e Memory, US Department of Commerce China Export Bans)
7. Financial Valuation & Quantitative Modeling (Discounted Cash Flow / DCF, WACC, Multiples Benchmarking vs Big Tech)
8. Multi-Dimensional Risk Matrix (Customer Concentration, Hyperscaler Custom Silicon, Cyclicality)
9. Forward Guidance & 5-Year Scenario Analysis (Bull, Base, Bear Cases)
10. Data Provenance, Resilience Log & Fallback Audit Trail
"""


