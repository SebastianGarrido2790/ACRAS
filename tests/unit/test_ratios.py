"""Unit tests for domain financial ratio extraction."""

import math

from src.tier2_simulation.ratios import compute_financial_ratios


def test_compute_financial_ratios_returns_expected_values() -> None:
    """The extractor should map canonical feature names to standardized ratios."""
    raw_features = {
        "current_assets": 150.0,
        "current_liabilities": 75.0,
        "quick_assets": 90.0,
        "total_debt": 200.0,
        "total_equity": 100.0,
        "net_income": 50.0,
        "total_revenue": 400.0,
        "operating_profit": 80.0,
        "ebit": 100.0,
        "interest_expense": 20.0,
        "total_assets": 200.0,
    }

    ratios = compute_financial_ratios(raw_features)

    assert ratios["current_ratio"] == 2.0
    assert ratios["quick_ratio"] == 1.2
    assert ratios["debt_to_equity"] == 2.0
    assert ratios["net_profit_margin"] == 0.125
    assert ratios["ebitda_margin"] == 0.2
    assert ratios["interest_coverage"] == 5.0
    assert ratios["asset_turnover"] == 2.0
    assert all(math.isfinite(value) for value in ratios.values())


def test_compute_financial_ratios_handles_zero_division_safely() -> None:
    """Zero denominators should never leak NaN or inf into the output bundle."""
    raw_features = {
        "current_assets": 100.0,
        "current_liabilities": 0.0,
        "quick_assets": 60.0,
        "total_debt": 10.0,
        "total_equity": 0.0,
        "net_income": 20.0,
        "total_revenue": 0.0,
        "operating_profit": 5.0,
        "ebit": 30.0,
        "interest_expense": 0.0,
        "total_assets": 0.0,
    }

    ratios = compute_financial_ratios(raw_features)

    assert ratios["current_ratio"] == 999.0
    assert ratios["quick_ratio"] == 999.0
    assert ratios["debt_to_equity"] == 999.0
    assert ratios["net_profit_margin"] == 999.0
    assert ratios["ebitda_margin"] == 999.0
    assert ratios["interest_coverage"] == 999.0
    assert ratios["asset_turnover"] == 0.0
    assert all(math.isfinite(value) for value in ratios.values())
