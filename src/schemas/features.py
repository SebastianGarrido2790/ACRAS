"""Canonical Feature Schema and Specifications.

Governed by:
    INV-2 (ADR-002): Structured data contract boundaries.
    D-1.10 (ADR-024): Resolution of duplicate feature column.
        ' Current Liability to Liability' is dropped due to exact identity (r = 1.000)
        with ' Current Liabilities/Liability'.
    D-1.8 (ADR-023): Single canonical feature list imported by training pipelines,
        evaluation gates, and runtime FastAPI validators.
"""

from __future__ import annotations

#: The target classification label in the Taiwan Bankruptcy dataset.
TARGET_COLUMN: str = "Bankrupt?"

#: Duplicate feature dropped per D-1.10 / ADR-024.
DROPPED_DUPLICATE_FEATURE: str = " Current Liability to Liability"

#: The duplicate feature retained to match the '/' ratio naming convention.
RETAINED_DUPLICATE_FEATURE: str = " Current Liabilities/Liability"

#: Exact tuple of 94 clean feature column names, in fixed order.
#: Corresponds to the 95 raw features in data/raw/data.csv minus DROPPED_DUPLICATE_FEATURE.
CANONICAL_FEATURES: tuple[str, ...] = (
    " ROA(C) before interest and depreciation before interest",
    " ROA(A) before interest and % after tax",
    " ROA(B) before interest and depreciation after tax",
    " Operating Gross Margin",
    " Realized Sales Gross Margin",
    " Operating Profit Rate",
    " Pre-tax net Interest Rate",
    " After-tax net Interest Rate",
    " Non-industry income and expenditure/revenue",
    " Continuous interest rate (after tax)",
    " Operating Expense Rate",
    " Research and development expense rate",
    " Cash flow rate",
    " Interest-bearing debt interest rate",
    " Tax rate (A)",
    " Net Value Per Share (B)",
    " Net Value Per Share (A)",
    " Net Value Per Share (C)",
    " Persistent EPS in the Last Four Seasons",
    " Cash Flow Per Share",
    " Revenue Per Share (Yuan \u00a5)",
    " Operating Profit Per Share (Yuan \u00a5)",
    " Per Share Net profit before tax (Yuan \u00a5)",
    " Realized Sales Gross Profit Growth Rate",
    " Operating Profit Growth Rate",
    " After-tax Net Profit Growth Rate",
    " Regular Net Profit Growth Rate",
    " Continuous Net Profit Growth Rate",
    " Total Asset Growth Rate",
    " Net Value Growth Rate",
    " Total Asset Return Growth Rate Ratio",
    " Cash Reinvestment %",
    " Current Ratio",
    " Quick Ratio",
    " Interest Expense Ratio",
    " Total debt/Total net worth",
    " Debt ratio %",
    " Net worth/Assets",
    " Long-term fund suitability ratio (A)",
    " Borrowing dependency",
    " Contingent liabilities/Net worth",
    " Operating profit/Paid-in capital",
    " Net profit before tax/Paid-in capital",
    " Inventory and accounts receivable/Net value",
    " Total Asset Turnover",
    " Accounts Receivable Turnover",
    " Average Collection Days",
    " Inventory Turnover Rate (times)",
    " Fixed Assets Turnover Frequency",
    " Net Worth Turnover Rate (times)",
    " Revenue per person",
    " Operating profit per person",
    " Allocation rate per person",
    " Working Capital to Total Assets",
    " Quick Assets/Total Assets",
    " Current Assets/Total Assets",
    " Cash/Total Assets",
    " Quick Assets/Current Liability",
    " Cash/Current Liability",
    " Current Liability to Assets",
    " Operating Funds to Liability",
    " Inventory/Working Capital",
    " Inventory/Current Liability",
    " Current Liabilities/Liability",
    " Working Capital/Equity",
    " Current Liabilities/Equity",
    " Long-term Liability to Current Assets",
    " Retained Earnings to Total Assets",
    " Total income/Total expense",
    " Total expense/Assets",
    " Current Asset Turnover Rate",
    " Quick Asset Turnover Rate",
    " Working capitcal Turnover Rate",
    " Cash Turnover Rate",
    " Cash Flow to Sales",
    " Fixed Assets to Assets",
    " Current Liability to Equity",
    " Equity to Long-term Liability",
    " Cash Flow to Total Assets",
    " Cash Flow to Liability",
    " CFO to Assets",
    " Cash Flow to Equity",
    " Current Liability to Current Assets",
    " Liability-Assets Flag",
    " Net Income to Total Assets",
    " Total assets to GNP price",
    " No-credit Interval",
    " Gross Profit to Sales",
    " Net Income to Stockholder's Equity",
    " Liability to Equity",
    " Degree of Financial Leverage (DFL)",
    " Interest Coverage Ratio (Interest expense to EBIT)",
    " Net Income Flag",
    " Equity to Liability",
)

#: Assert exactly 94 canonical features at import time.
assert (
    len(CANONICAL_FEATURES) == 94
), f"Expected 94 canonical features, got {len(CANONICAL_FEATURES)}"
assert DROPPED_DUPLICATE_FEATURE not in CANONICAL_FEATURES
assert RETAINED_DUPLICATE_FEATURE in CANONICAL_FEATURES
