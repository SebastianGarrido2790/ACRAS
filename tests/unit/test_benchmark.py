"""Unit tests for the Vasicek analytical benchmark and tolerance gate."""

import math

from scipy.stats import norm

from src.tier2_simulation.benchmark import (
    vasicek_cdf,
    vasicek_pdf,
    vasicek_quantile,
    verify_simulation_benchmark,
)


def test_vasicek_quantile_matches_closed_form() -> None:
    """The quantile should match the closed-form Vasicek expression exactly."""
    p = 0.03
    rho = 0.15
    for alpha in (0.10, 0.50, 0.90):
        expected = norm.cdf(
            (norm.ppf(p) + math.sqrt(rho) * norm.ppf(alpha)) / math.sqrt(1.0 - rho)
        )
        actual = vasicek_quantile(p=p, rho=rho, alpha=alpha)
        assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)


def test_vasicek_pdf_and_cdf_are_finite_and_ordered() -> None:
    """The distribution evaluation helpers should remain finite on valid domain inputs."""
    p = 0.03
    rho = 0.15
    for x in (0.05, 0.25, 0.90):
        cdf_value = vasicek_cdf(x=x, p=p, rho=rho)
        pdf_value = vasicek_pdf(x=x, p=p, rho=rho)
        assert 0.0 <= cdf_value <= 1.0
        assert math.isfinite(cdf_value)
        assert math.isfinite(pdf_value)
        assert pdf_value >= 0.0


def test_verify_simulation_benchmark_accepts_valid_band_and_rejects_corruption() -> None:
    """Exact analytical bands should pass, while a drifted band should be rejected."""
    p = 0.03
    rho = 0.15
    tolerances = {"p10": 0.015, "p50": 0.015, "p90": 0.020}

    valid_band = {
        "p10": vasicek_quantile(p, rho, 0.10),
        "p50": vasicek_quantile(p, rho, 0.50),
        "p90": vasicek_quantile(p, rho, 0.90),
    }

    is_valid, metrics = verify_simulation_benchmark(valid_band, p, rho, tolerances)
    assert is_valid is True
    assert metrics["max_delta"] <= 1e-12

    corrupted_band = dict(valid_band)
    corrupted_band["p90"] = min(1.0, valid_band["p90"] + 0.05)
    is_valid, metrics = verify_simulation_benchmark(corrupted_band, p, rho, tolerances)
    assert is_valid is False
    assert metrics["p90_delta"] > 0.0
    assert metrics["max_delta"] == metrics["p90_delta"]
