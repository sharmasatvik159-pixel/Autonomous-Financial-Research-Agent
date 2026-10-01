"""Evaluation framework for ARA-1.

Implements automated and LLM-as-a-judge metrics across 5 categories (20+ metrics):
1. Factual Accuracy (FA-1 to FA-5)
2. Completeness (CO-1 to CO-4)
3. Analytical Depth (AD-1 to AD-4)
4. Coherence and Structure (CS-1 to CS-4)
5. Agent Behavior (AB-1 to AB-5)
"""

from evaluation.metrics import (
    MetricScore,
    ReportEvaluationResult,
    evaluate_report,
    evaluate_results_directory,
    ALL_EVALUATORS,
)
from evaluation.benchmarks import (
    MSFT_BENCHMARK,
    AAPL_BENCHMARK,
    TSLA_BENCHMARK,
    BENCHMARKS,
    get_benchmark,
    load_all_benchmarks,
)
from evaluation.dashboard import (
    generate_evaluation_markdown,
    run_dashboard_cli,
)

__all__ = [
    "MetricScore",
    "ReportEvaluationResult",
    "evaluate_report",
    "evaluate_results_directory",
    "ALL_EVALUATORS",
    "MSFT_BENCHMARK",
    "AAPL_BENCHMARK",
    "TSLA_BENCHMARK",
    "BENCHMARKS",
    "get_benchmark",
    "load_all_benchmarks",
    "generate_evaluation_markdown",
    "run_dashboard_cli",
]
