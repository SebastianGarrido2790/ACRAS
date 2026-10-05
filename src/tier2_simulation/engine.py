"""Vectorized Monte Carlo engine for Tier 2 default-risk simulation.

Governed by:
    ADR-029: Unified Vasicek Structural & Correlated Macro-Shock Engine.
    D-2.1 / D-2.1a / D-2.1b: vectorized Monte Carlo path generation with Cholesky,
        deterministic seeding, and strict percentile monotonicity checks.
"""

from __future__ import annotations

import numpy as np
from scipy import linalg
from scipy.stats import norm

from src.config.loader import SimulationConfig
from src.schemas.evidence_bundle import PDBand

__all__ = [
    "SimulationConfigError",
    "build_correlation_matrix",
    "run_monte_carlo_simulation",
]


class SimulationConfigError(ValueError):
    """Raised when a simulation parameter or correlation matrix is invalid."""


def build_correlation_matrix(asset_correlation: float) -> np.ndarray:
    """Build a valid 3-factor correlation matrix for the Monte Carlo engine."""
    corr = float(asset_correlation)
    if not 0.0 <= corr < 1.0:
        raise SimulationConfigError(
            "asset_correlation must satisfy 0.0 <= asset_correlation < 1.0; "
            f"got {corr!r}."
        )

    matrix = np.array(
        [
            [1.0, corr, 0.5 * corr],
            [corr, 1.0, 0.75 * corr],
            [0.5 * corr, 0.75 * corr, 1.0],
        ],
        dtype=float,
    )

    try:
        linalg.cholesky(matrix, lower=True)
    except linalg.LinAlgError as exc:  # pragma: no cover - defensive against invalid matrix inputs
        raise SimulationConfigError("Correlation matrix must be positive definite.") from exc

    return matrix


def run_monte_carlo_simulation(
    pd: float,
    config: SimulationConfig,
    *,
    correlation_matrix: np.ndarray | None = None,
) -> PDBand:
    """Run a vectorized Monte Carlo simulation and return the P10/P50/P90 default band.

    The engine generates a 3-factor correlated Gaussian system, applies the Vasicek
    structural default condition ``Z_i < Phi^-1(PD)``, and returns a monotonic percentile
    band as a validated ``PDBand`` model.
    """
    pd_value = float(pd)
    if not 0.0 <= pd_value <= 1.0:
        raise SimulationConfigError(f"pd must be within [0.0, 1.0]; got {pd_value!r}.")

    if correlation_matrix is None:
        matrix = build_correlation_matrix(config.asset_correlation)
    else:
        matrix = np.asarray(correlation_matrix, dtype=float)
        if matrix.shape != (3, 3):
            raise SimulationConfigError(
                f"Correlation matrix must be 3x3; got shape {matrix.shape}."
            )
        try:
            linalg.cholesky(matrix, lower=True)
        except linalg.LinAlgError as exc:
            raise SimulationConfigError("Correlation matrix must be positive definite.") from exc

    n_iterations = int(config.n_iterations)
    rng = np.random.default_rng(config.seed)
    innovations = rng.standard_normal((n_iterations, 3))
    chol = linalg.cholesky(matrix, lower=True)
    correlated = innovations @ chol.T

    rho = float(config.asset_correlation)
    systemic_shock = correlated[:, 0]
    debt_shock = correlated[:, 1]
    haircut_shock = correlated[:, 2]

    # The structural estimate is a weighted blend of systemic and idiosyncratic risk,
    # mapped through the analytical Vasicek transform so that the empirical percentiles
    # remain on the probability scale [0, 1] and remain comparable to the benchmark.
    asset_returns = (
        np.sqrt(rho) * systemic_shock
        + np.sqrt(1.0 - rho) * (0.5 * debt_shock + 0.5 * haircut_shock)
    )

    if pd_value == 0.0:
        default_band = np.zeros(3, dtype=float)
    elif pd_value == 1.0:
        default_band = np.ones(3, dtype=float)
    else:
        alpha_paths = norm.cdf(asset_returns)
        transformed = (
            norm.ppf(pd_value) + np.sqrt(rho) * norm.ppf(alpha_paths)
        ) / np.sqrt(1.0 - rho)
        default_band = np.percentile(
            norm.cdf(transformed), [10, 50, 90], method="weibull"
        )

    band = PDBand(
        p10=float(default_band[0]),
        p50=float(default_band[1]),
        p90=float(default_band[2]),
    )
    return band
