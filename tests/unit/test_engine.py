"""Unit tests for the vectorized Monte Carlo simulation engine."""

import numpy as np
import pytest

from src.config.loader import SimulationConfig
from src.tier2_simulation.benchmark import verify_simulation_benchmark
from src.tier2_simulation.engine import SimulationConfigError, run_monte_carlo_simulation


def _base_config() -> SimulationConfig:
    return SimulationConfig(
        n_iterations=10_000,
        seed=42,
        asset_correlation=0.15,
        tolerance_p10=0.015,
        tolerance_p50=0.015,
        tolerance_p90=0.020,
        latency_budget_ms=5.0,
        macro_volatility=0.20,
        debt_service_shock_std=0.15,
        asset_haircut_std=0.10,
    )


def test_monte_carlo_engine_seed_reproducibility() -> None:
    """Identical seeds must yield bitwise-identical percentile outputs."""
    config = _base_config()

    first = run_monte_carlo_simulation(pd=0.03, config=config)
    second = run_monte_carlo_simulation(pd=0.03, config=config)

    assert first == second
    assert first.p10 == pytest.approx(first.p10)
    assert first.p50 == pytest.approx(first.p50)
    assert first.p90 == pytest.approx(first.p90)


def test_monte_carlo_engine_degenerate_probability_cases() -> None:
    """Degenerate PD values should collapse to a trivial distribution at the endpoints."""
    config = _base_config()

    zero_band = run_monte_carlo_simulation(pd=0.0, config=config)
    one_band = run_monte_carlo_simulation(pd=1.0, config=config)

    assert zero_band.p10 == 0.0
    assert zero_band.p50 == 0.0
    assert zero_band.p90 == 0.0

    assert one_band.p10 == 1.0
    assert one_band.p50 == 1.0
    assert one_band.p90 == 1.0


def test_monte_carlo_engine_matches_benchmark_tolerance() -> None:
    """The Monte Carlo band should land within the analytical tolerance gate for a fixed seed."""
    config = _base_config()
    simulated = run_monte_carlo_simulation(pd=0.03, config=config)
    band = {"p10": float(simulated.p10), "p50": float(simulated.p50), "p90": float(simulated.p90)}

    is_valid, metrics = verify_simulation_benchmark(band, p=0.03, rho=0.15, tolerances={
        "p10": config.tolerance_p10,
        "p50": config.tolerance_p50,
        "p90": config.tolerance_p90,
    })
    assert is_valid is True
    assert metrics["max_delta"] <= 0.02


def test_monte_carlo_engine_rejects_invalid_correlation_matrix() -> None:
    """A non-positive-definite correlation matrix should raise the typed domain error."""
    config = _base_config()
    bad_matrix = np.array(
        [
            [1.0, 0.9, 0.9],
            [0.9, 1.0, 0.9],
            [0.9, 0.9, 1.0],
        ],
        dtype=float,
    )
    bad_matrix[2, 2] = 0.2

    with pytest.raises(SimulationConfigError, match="Correlation matrix"):
        run_monte_carlo_simulation(pd=0.03, config=config, correlation_matrix=bad_matrix)
