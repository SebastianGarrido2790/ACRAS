"""Great Expectations Data Contract Pipeline Module.

Enforces deterministic schema, dtype, null-rate, range, and uniqueness invariants
on corporate financial bankruptcy datasets prior to downstream feature engineering
or model training (governed by INV-7 and ADR-007 / ADR-013).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import great_expectations as gx
import great_expectations.expectations.core as gxe
import pandas as pd
from great_expectations.data_context import AbstractDataContext

SUITE_NAME: str = "bankruptcy_data_suite"

RAW_DATA_COLUMNS: tuple[str, ...] = (
    "Bankrupt?",
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
    " Current Liability to Liability",
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

KEY_FINANCIAL_RATIOS: tuple[str, ...] = (
    " ROA(A) before interest and % after tax",
    " Operating Gross Margin",
    " Net Income to Total Assets",
    " Debt ratio %",
    " Net worth/Assets",
    " Borrowing dependency",
    " Current Assets/Total Assets",
    " Working Capital to Total Assets",
    " Cash/Total Assets",
    " Interest Coverage Ratio (Interest expense to EBIT)",
    " Cash Flow to Total Assets",
)

UNIQUENESS_SUBSET: tuple[str, ...] = (
    " ROA(A) before interest and % after tax",
    " Operating Gross Margin",
    " Net Income to Total Assets",
    " Debt ratio %",
    " Net worth/Assets",
    " Cash/Total Assets",
)


def build_bankruptcy_suite(
    context: AbstractDataContext | None = None,
) -> gx.ExpectationSuite:
    """Build and return the formal Great Expectations suite for raw bankruptcy data.

    If a data context is provided, the suite is registered/persisted into the context.

    Args:
        context: Optional Great Expectations DataContext instance.

    Returns:
        Configured ExpectationSuite instance.
    """
    if context is None:
        context = gx.get_context(mode="file")
    assert context is not None

    suite = gx.ExpectationSuite(name=SUITE_NAME)

    # 1. Table structure and schema
    suite.add_expectation(gxe.ExpectTableColumnCountToEqual(value=len(RAW_DATA_COLUMNS)))
    suite.add_expectation(
        gxe.ExpectTableRowCountToBeBetween(min_value=6000, max_value=7500)
    )
    suite.add_expectation(
        gxe.ExpectTableColumnsToMatchSet(
            column_set=list(RAW_DATA_COLUMNS), exact_match=True
        )
    )

    # 2. Target variable (Bankrupt?)
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="Bankrupt?"))
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeInSet(column="Bankrupt?", value_set=[0, 1])
    )
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeOfType(column="Bankrupt?", type_="int64")
    )

    # 3. Categorical Flags
    suite.add_expectation(
        gxe.ExpectColumnValuesToNotBeNull(column=" Liability-Assets Flag")
    )
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeInSet(
            column=" Liability-Assets Flag", value_set=[0, 1]
        )
    )
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeOfType(
            column=" Liability-Assets Flag", type_="int64"
        )
    )

    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column=" Net Income Flag"))
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeInSet(column=" Net Income Flag", value_set=[1])
    )
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeOfType(column=" Net Income Flag", type_="int64")
    )

    # 4. Key Financial Ratios (Profitability, Solvency, Liquidity, Coverage)
    for col in KEY_FINANCIAL_RATIOS:
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column=col))
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeBetween(
                column=col, min_value=0.0, max_value=1.0
            )
        )
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeOfType(column=col, type_="float64")
        )

    # 5. Entity Uniqueness Invariant (zero duplicated financial footprints)
    suite.add_expectation(
        gxe.ExpectCompoundColumnsToBeUnique(column_list=list(UNIQUENESS_SUBSET))
    )

    if context is not None:
        suite = context.suites.add_or_update(suite)

    return suite


def validate_dataset(
    csv_path: Path | str,
    suite: gx.ExpectationSuite | None = None,
    context: AbstractDataContext | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Validate a CSV dataset against the formal bankruptcy data contract.

    Args:
        csv_path: Path to the CSV file to validate.
        suite: Optional ExpectationSuite. If None, builds default suite.
        context: Optional Great Expectations DataContext.

    Returns:
        Tuple of (success_boolean, summary_dictionary).
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset file not found at: {path}")

    if context is None:
        context = gx.get_context(mode="file")
    assert context is not None

    if suite is None:
        try:
            suite = context.suites.get(SUITE_NAME)
        except Exception:
            suite = build_bankruptcy_suite(context=context)

    df = pd.read_csv(path)

    # Configure transient batch for validation
    ds_name = f"validation_ds_{path.stem}"
    try:
        data_source = context.data_sources.get(ds_name)
    except Exception:
        data_source = context.data_sources.add_pandas(ds_name)

    asset_name = f"asset_{path.stem}"
    try:
        asset = data_source.get_asset(asset_name)
    except Exception:
        asset = data_source.add_dataframe_asset(asset_name)

    batch_def_name = f"batch_def_{path.stem}"
    try:
        batch_def = asset.get_batch_definition(batch_def_name)
    except Exception:
        batch_def = asset.add_batch_definition_whole_dataframe(batch_def_name)

    batch = batch_def.get_batch(batch_parameters={"dataframe": df})
    validation_result = batch.validate(suite)

    success = bool(validation_result.success)
    evaluated = len(validation_result.results)
    failed = [r for r in validation_result.results if not r.success]

    summary: dict[str, Any] = {
        "dataset_path": str(path),
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "total_expectations": evaluated,
        "failed_expectations_count": len(failed),
        "success": success,
        "failed_details": [
            {
                "expectation_type": f.expectation_config.type
                if f.expectation_config
                else "unknown",
                "result": f.result,
            }
            for f in failed
        ],
    }

    return success, summary


def main() -> None:
    """CLI entrypoint for Great Expectations data contract validation."""
    parser = argparse.ArgumentParser(
        description="ACRAS Data Contract Validation (Great Expectations Suite)"
    )
    parser.add_argument(
        "dataset",
        nargs="?",
        default="data/raw/data.csv",
        help="Path to the dataset CSV file (default: data/raw/data.csv)",
    )
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Build and persist the expectation suite without running validation",
    )
    args = parser.parse_args()

    context = gx.get_context(mode="file")

    if args.build_only:
        suite = build_bankruptcy_suite(context=context)
        print(
            f"[data_contracts] Successfully compiled and saved suite '{suite.name}' with "
            f"{len(suite.expectations)} expectations."
        )
        sys.exit(0)

    print(f"[data_contracts] Validating dataset: {args.dataset}")
    try:
        success, summary = validate_dataset(csv_path=args.dataset, context=context)
    except Exception as exc:
        print(f"[data_contracts] ERROR during validation execution: {exc}", file=sys.stderr)
        sys.exit(2)

    print(
        f"[data_contracts] Total evaluated: {summary['total_expectations']} | "
        f"Failed: {summary['failed_expectations_count']} | "
        f"Success: {summary['success']}"
    )

    if not success:
        print("[data_contracts] FAILED: Data contract violations detected!", file=sys.stderr)
        for item in summary["failed_details"]:
            print(f"  - {item['expectation_type']}: {item['result']}", file=sys.stderr)
        sys.exit(1)

    print("[data_contracts] PASS: Data contract 100% satisfied.")
    sys.exit(0)


if __name__ == "__main__":
    main()
