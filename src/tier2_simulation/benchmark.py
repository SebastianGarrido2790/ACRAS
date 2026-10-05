"""Analytical benchmark functions for Vasicek default-probability validation.

Governed by:
    ADR-030: Closed-form Vasicek analytical verification benchmark.
    D-2.2: The benchmark is the ground-truth reference against which the Monte Carlo
        Tier 2 engine is validated.
"""

from __future__ import annotations

import math

from scipy.stats import norm

__all__ = [
    "vasicek_cdf",
    "vasicek_pdf",
    "vasicek_quantile",
    "verify_simulation_benchmark",
]


def _clamp_probability(value: float, *, lower: float = 1e-12, upper: float = 1.0 - 1e-12) -> float:
    """Clamp probability-like values into the valid open interval (0, 1)."""
    return min(max(float(value), lower), upper)


def vasicek_quantile(p: float, rho: float, alpha: float) -> float:
    """Compute the closed-form Vasicek quantile for a probability-of-default band.

    q_alpha = Phi((Phi^-1(p) + sqrt(rho) * Phi^-1(alpha)) / sqrt(1-rho))
    """
    p_value = _clamp_probability(p)
    rho_value = min(max(float(rho), 0.0), 1.0)
    alpha_value = _clamp_probability(alpha)

    numerator = norm.ppf(p_value) + math.sqrt(rho_value) * norm.ppf(alpha_value)
    denominator = math.sqrt(1.0 - rho_value)
    return float(norm.cdf(numerator / denominator))


def vasicek_pdf(x: float, p: float, rho: float) -> float:
    """Evaluate the Vasicek benchmark PDF at a probability x in (0, 1)."""
    x_value = _clamp_probability(x)
    p_value = _clamp_probability(p)
    rho_value = min(max(float(rho), 0.0), 1.0)

    g_x = (
        norm.ppf(p_value) + math.sqrt(rho_value) * norm.ppf(x_value)
    ) / math.sqrt(1.0 - rho_value)
    derivative = (
        math.sqrt(rho_value) / math.sqrt(1.0 - rho_value)
    ) / norm.pdf(norm.ppf(x_value))
    return float(norm.pdf(g_x) * derivative)


def vasicek_cdf(x: float, p: float, rho: float) -> float:
    """Evaluate the closed-form Vasicek CDF at a probability x in (0, 1)."""
    x_value = _clamp_probability(x)
    return vasicek_quantile(p=p, rho=rho, alpha=x_value)


def verify_simulation_benchmark(
    simulated_band: dict[str, float],
    p: float,
    rho: float,
    tolerances: dict[str, float],
) -> tuple[bool, dict[str, float]]:
    """Compare a simulated PD band to the analytical Vasicek expectation.

    Returns a tuple of (is_valid, metrics), where metrics includes the absolute deltas
    for p10, p50, and p90. The function is deterministic and pure: it never mutates
    inputs and only depends on the analytical formula and configured tolerances.
    """
    analytical = {
        "p10": vasicek_quantile(p, rho, 0.10),
        "p50": vasicek_quantile(p, rho, 0.50),
        "p90": vasicek_quantile(p, rho, 0.90),
    }

    errors: dict[str, float] = {}
    for key in ("p10", "p50", "p90"):
        simulated_value = float(simulated_band[key])
        error = abs(simulated_value - analytical[key])
        errors[f"{key}_delta"] = error

    max_delta = max(errors.values(), default=0.0)
    is_valid = all(
        errors[f"{key}_delta"] <= float(tolerances[key])
        for key in ("p10", "p50", "p90")
    )

    metrics: dict[str, float] = {
        **errors,
        "max_delta": max_delta,
        "p10_analytical": analytical["p10"],
        "p50_analytical": analytical["p50"],
        "p90_analytical": analytical["p90"],
    }
    return is_valid, metrics
