"""Characterization + Tier 2 parameter-sensitivity tests (W-A7 / R-01, R-09).

These pin current behavior. They intentionally do NOT assert a `ValueError` for
missing ratio inputs: the required-input guard does not exist yet, and adding it
is deferred to post-Wave-A work. A raw benchmark row still yields seven 0.0
ratios; the remedy is an input-contract decision, not this characterization.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.config.loader import load_params
from src.schemas.features import CANONICAL_FEATURES
from src.tier2_simulation.engine import run_monte_carlo_simulation
from src.tier2_simulation.ratios import compute_financial_ratios

RAW_DATA = Path("data/raw/data.csv")


def test_raw_dataset_row_yields_seven_zero_ratios() -> None:
    """Characterization (R-01): a raw benchmark row yields seven 0.0 ratios.

    No `ValueError` is raised because the required-input guard does not exist
    yet; this test pins the observed current behavior, not a desired future one.
    """
    if not RAW_DATA.exists():
        pytest.skip("Raw dataset not present.")

    df = pd.read_csv(RAW_DATA)
    row = df[list(CANONICAL_FEATURES)].iloc[0].to_dict()

    ratios = compute_financial_ratios(row)

    assert len(ratios) == 7
    assert all(value == 0.0 for value in ratios.values())


def test_accounting_inputs_produce_nonzero_ratios() -> None:
    """The extractor is correct when given its expected accounting inputs.

    This isolates the defect to the input contract (ratio-like dataset columns),
    not the ratio arithmetic itself.
    """
    ratios = compute_financial_ratios(
        {
            "current_assets": 100.0,
            "current_liabilities": 50.0,
            "quick_assets": 80.0,
            "total_debt": 40.0,
            "total_equity": 60.0,
            "net_income": 10.0,
            "total_revenue": 200.0,
            "operating_profit": 30.0,
            "ebit": 25.0,
            "interest_expense": 5.0,
            "total_assets": 400.0,
        }
    )

    assert ratios["current_ratio"] == pytest.approx(2.0)
    assert ratios["quick_ratio"] == pytest.approx(1.6)
    assert ratios["debt_to_equity"] == pytest.approx(40.0 / 60.0)
    assert ratios["net_profit_margin"] == pytest.approx(0.05)
    assert ratios["ebitda_margin"] == pytest.approx(0.15)
    assert ratios["interest_coverage"] == pytest.approx(5.0)
    assert ratios["asset_turnover"] == pytest.approx(0.5)
    assert all(value != 0.0 for value in ratios.values())


def test_unused_shock_parameters_have_zero_effect() -> None:
    """`macro_volatility`, `debt_service_shock_std`, `asset_haircut_std` are dead config.

    R-09: the engine consumes only `asset_correlation`, `n_iterations`, and `seed`.
    Note: 10x on `macro_volatility` would exceed its `le=1.0` bound, so its maximum
    (1.0, 5x) is used; the other two are perturbed 10x.
    """
    sim = load_params().simulation
    base = run_monte_carlo_simulation(0.05, sim)

    perturbed_cfg = sim.model_copy(
        update={
            "macro_volatility": 1.0,
            "debt_service_shock_std": 1.5,
            "asset_haircut_std": 1.0,
        }
    )
    perturbed = run_monte_carlo_simulation(0.05, perturbed_cfg)

    assert (base.p10, base.p50, base.p90) == (perturbed.p10, perturbed.p50, perturbed.p90)


def test_asset_correlation_sweep_widens_band() -> None:
    """Higher `asset_correlation` widens the P10–P90 band monotonically (R-09)."""
    sim = load_params().simulation
    bands = [
        run_monte_carlo_simulation(
            0.05, sim.model_copy(update={"asset_correlation": rho})
        )
        for rho in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30)
    ]

    for band in bands:
        assert band.p10 <= band.p50 <= band.p90

    widths = [band.p90 - band.p10 for band in bands]
    assert all(later > earlier for earlier, later in zip(widths, widths[1:]))

    p90s = [band.p90 for band in bands]
    assert all(later >= earlier for earlier, later in zip(p90s, p90s[1:]))
