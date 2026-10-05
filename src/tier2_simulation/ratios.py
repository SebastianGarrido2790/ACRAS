"""Deterministic financial ratio extraction for Tier 2 evidence enrichment.

Governed by:
    ADR-033: Deterministic Financial Ratio Extraction Module.
    PRD FR5: persona-level interpretation depends on stable financial ratios derived
        from verified raw features without introducing NaN/inf contamination.
"""

from __future__ import annotations

import math

__all__ = ["compute_financial_ratios"]


def _normalize_key(value: str) -> str:
    """Normalize a raw feature key so free-form labels match canonical aliases."""
    return "".join(character for character in value.lower() if character.isalnum())


def _lookup(raw_features: dict[str, float | int], *candidate_names: str) -> float:
    """Return the first resolved numeric value from a set of acceptable aliases."""
    normalized = {
        _normalize_key(str(key)): float(value)
        for key, value in raw_features.items()
        if key is not None and value is not None
    }

    for candidate in candidate_names:
        lookup_key = _normalize_key(candidate)
        if lookup_key in normalized:
            return normalized[lookup_key]
    return 0.0


def _safe_ratio(
    numerator: float,
    denominator: float,
    *,
    fallback: float = 999.0,
    negative_fallback: float = -999.0,
) -> float:
    """Compute a ratio without allowing division-by-zero or non-finite values to escape."""
    if not math.isfinite(numerator) or not math.isfinite(denominator):
        return 0.0

    if denominator == 0.0:
        if numerator > 0.0:
            return float(fallback)
        if numerator < 0.0:
            return float(negative_fallback)
        return 0.0

    ratio = numerator / denominator
    if not math.isfinite(ratio):
        if numerator > 0.0:
            return float(fallback)
        if numerator < 0.0:
            return float(negative_fallback)
        return 0.0

    return float(ratio)


def compute_financial_ratios(raw_features: dict[str, float | int]) -> dict[str, float]:
    """Compute deterministically stable credit-risk ratios from verified raw features.

    The function accepts a broad set of common aliases for the same accounting inputs so it
    remains robust to upstream naming drift while returning only finite float values.
    """
    current_assets = _lookup(
        raw_features,
        "current_assets",
        "current assets",
        "total current assets",
    )
    current_liabilities = _lookup(
        raw_features,
        "current_liabilities",
        "current liabilities",
        "total current liabilities",
    )
    quick_assets = _lookup(raw_features, "quick_assets", "quick assets", "quick assets total")
    total_debt = _lookup(raw_features, "total_debt", "total debt", "debt")
    total_equity = _lookup(raw_features, "total_equity", "total equity", "equity")
    net_income = _lookup(raw_features, "net_income", "net income")
    total_revenue = _lookup(raw_features, "total_revenue", "total revenue", "revenue")
    operating_profit = _lookup(
        raw_features,
        "operating_profit",
        "operating profit",
        "ebitda",
    )
    ebit = _lookup(raw_features, "ebit", "ebit")
    interest_expense = _lookup(raw_features, "interest_expense", "interest expense")
    total_assets = _lookup(raw_features, "total_assets", "total assets", "assets")

    ratios = {
        "current_ratio": _safe_ratio(current_assets, current_liabilities),
        "quick_ratio": _safe_ratio(quick_assets, current_liabilities),
        "debt_to_equity": _safe_ratio(total_debt, total_equity),
        "net_profit_margin": _safe_ratio(net_income, total_revenue),
        "ebitda_margin": _safe_ratio(operating_profit, total_revenue),
        "interest_coverage": _safe_ratio(ebit, interest_expense),
        "asset_turnover": _safe_ratio(total_revenue, total_assets),
    }

    return {name: float(value) for name, value in ratios.items()}
