"""Benchmarks package for ARA-1.

Houses human analyst baseline datasets (e.g. Goldman Sachs, Morgan Stanley equity reports)
and evaluation benchmarks for research challenges.
"""

from evaluation.benchmarks.analyst_benchmarks import (
    MSFT_BENCHMARK,
    AAPL_BENCHMARK,
    TSLA_BENCHMARK,
    NVDA_BENCHMARK,
    BENCHMARKS,
    get_benchmark,
    load_all_benchmarks,
)

__all__ = [
    "MSFT_BENCHMARK",
    "AAPL_BENCHMARK",
    "TSLA_BENCHMARK",
    "NVDA_BENCHMARK",
    "BENCHMARKS",
    "get_benchmark",
    "load_all_benchmarks",
]
