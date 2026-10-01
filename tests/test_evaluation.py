"""Unit tests for Evaluation Framework and Quality Metrics."""

import os
import pytest
from evaluation.benchmarks import get_benchmark, load_all_benchmarks
from evaluation.metrics import (
    evaluate_fa1_numerical_accuracy,
    evaluate_fa2_citation_validity,
    evaluate_fa3_temporal_correctness,
    evaluate_fa4_entity_accuracy,
    evaluate_fa5_zero_hallucinations,
    evaluate_co1_section_coverage,
    evaluate_co2_source_diversity,
    evaluate_co3_temporal_horizon,
    evaluate_co4_risk_factor_coverage,
    evaluate_ad1_insight_density,
    evaluate_ad2_cross_source_synthesis,
    evaluate_ad3_original_calculations,
    evaluate_ad4_forward_scenario_modeling,
    evaluate_cs1_markdown_structure,
    evaluate_cs2_table_presentation,
    evaluate_cs3_internal_consistency,
    evaluate_cs4_formatting_cleanliness,
    evaluate_ab1_tool_efficiency,
    evaluate_ab2_error_recovery,
    evaluate_ab3_planning_quality,
    evaluate_ab4_memory_utilization,
    evaluate_ab5_execution_efficiency,
    evaluate_report,
    evaluate_results_directory,
    ReportEvaluationResult,
)


def test_benchmarks_loaded():
    """Verify human analyst benchmarks exist for MSFT, AAPL, TSLA."""
    benchmarks = load_all_benchmarks()
    assert "MSFT" in benchmarks
    assert "AAPL" in benchmarks
    assert "TSLA" in benchmarks

    msft = get_benchmark("MSFT")
    assert msft["fiscal_year"] == 2024
    assert msft["ground_truth_metrics"]["revenue"] == 245.12

    aapl = get_benchmark("AAPL")
    assert aapl["ground_truth_metrics"]["reported_revenue"] == 94.93

    tsla = get_benchmark("TSLA")
    assert tsla["ground_truth_metrics"]["auto_gross_margin_ex_credits"] == 16.4


def test_ab4_memory_utilization_ratio_correction():
    """Verify AB-4 evaluates true ratio (memory_hits / total_calls), fixing document Error 1."""
    score = evaluate_ab4_memory_utilization({"memory_hits": 3, "total_api_calls": 5})
    assert score.score == 0.6
    assert score.passed is True
    assert "Rectified" in score.details or "ratio" in score.details.lower()


def test_fa5_hallucination_check():
    """Verify FA-5 catches forbidden placeholder strings."""
    clean_text = "# Clean Research\nTotal revenue reached $100M with 15% YoY growth."
    dirty_text = "# Bad Research\nTotal revenue was TODO and operating margin is null."

    pass_score = evaluate_fa5_zero_hallucinations(clean_text)
    assert pass_score.score == 1.0
    assert pass_score.passed is True

    fail_score = evaluate_fa5_zero_hallucinations(dirty_text)
    assert fail_score.score == 0.0
    assert fail_score.passed is False


def test_full_report_evaluation():
    """Verify evaluate_report aggregates all 22 metrics and returns composite score."""
    sample_report = """# Investment Research Profile: Test Corp (NASDAQ: TEST)
## 1. Executive Summary
Test Corp generated $100.0B in FY24 revenue (+15.0% YoY) and $40.0B in operating income (40.0% margin).
## 2. Business Overview & Segment Breakdown
Intelligent division expanded +25.0% YoY.
## 3. Financial Summary
| Metric | FY23 | FY24 | YoY |
| :--- | :--- | :--- | :--- |
| Revenue | $85B | $100B | +15% |
## 4. Key Risks & Forward Guidance
Forward guidance suggests low double-digit expansion with supply chain and regulatory risks.
## 5. Research Methodology
Source: SEC Form 10-K and financial_data_api.
"""
    result = evaluate_report(sample_report, report_name="test_report.md")
    assert isinstance(result, ReportEvaluationResult)
    assert len(result.scores) >= 20
    assert result.composite_score > 0.70
    assert result.category_scores["Coherence & Structure"] == 1.0


def test_evaluate_results_directory():
    """Verify evaluate_results_directory processes all available challenge files."""
    results_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "results"))
    results = evaluate_results_directory(results_dir)
    assert len(results) >= 7
    for fname in ["challenge_1.md", "challenge_2.md", "challenge_3.md"]:
        assert fname in results
        assert results[fname].composite_score >= 0.80
