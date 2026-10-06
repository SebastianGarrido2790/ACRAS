"""Vectorized Monte Carlo engine for Tier 2 default-risk simulation.

Governed by:
    INV-1 (ADR-001): Deterministic core invariant. Tier 2 is fully deterministic,
        reproducible under a fixed pseudo-random generator seed, and decoupled
        from non-deterministic LLM reasoning.
    INV-2 (ADR-002): Sole inter-tier contract. Simulation outputs emit strictly
        through the typed, immutable `PDBand` schema enforcing strict monotonicity
        (0.0 <= P10 <= P50 <= P90 <= 1.0).
    ADR-028 (D-2.0): Simulation hyperparameters loaded from validated `SimulationConfig`
        without inline magic numbers.
    ADR-029 (D-2.1, D-2.1a, D-2.1b): Unified Vasicek Structural & Correlated
        Macro-Shock Engine. Decomposes a 3-factor Gaussian system via Cholesky
        factorization (systemic macro shock, debt service coverage shock, and
        collateral haircut shock) into structural asset return innovations.
    ADR-030 (D-2.2): Closed-Form Vasicek Analytical Verification Benchmark. Empirical
        percentiles match the closed-form Vasicek distribution within configured
        absolute tolerances (|P_alpha - P_alpha_analytical| <= epsilon).
    PRD FR3 & FR11: Vectorized Monte Carlo engine executing N >= 10,000 paths
        within the sub-5.0ms latency budget.
    D-2.6: Latency SLA gate requiring P95 wall-clock execution time < 5.0 ms.

Mathematical Formulation:
    Under the Merton-Vasicek structural credit model (Basel II ASRF framework),
    a borrower defaults if normalized asset return Z falls below a default barrier:
        Z < Phi^-1(PD)
    where:
        Z = sqrt(rho) * X + sqrt(1 - rho) * epsilon
        X ~ N(0, 1) is the systemic market risk factor,
        epsilon ~ N(0, 1) is the idiosyncratic borrower risk factor,
        rho in [0, 1) is the asset correlation parameter.

    This engine extends the standard single-factor setup to a 3-variable correlated
    system Y = Z_innov * L^T, where L = cholesky(Sigma, lower=True) correlates:
        1. Systemic macro shock (factor 0)
        2. Debt service coverage shock (factor 1)
        3. Collateral asset haircut shock (factor 2)

    Asset return innovations are transformed into the conditional default probability
    scale via the analytical Vasicek structural mapping:
        q_alpha = Phi((Phi^-1(PD) + sqrt(rho) * Phi^-1(alpha)) / sqrt(1 - rho))
    where alpha = Phi(asset_returns). Empirical percentiles (P10, P50, P90) are
    computed across N paths using the Weibull interpolation method.
"""

from __future__ import annotations

import numpy as np
from scipy import linalg
from scipy.special import ndtr, ndtri

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
    """Build a symmetric positive-definite 3-factor correlation matrix.

    Constructs the correlation structure linking:
        - Factor 0: Systemic macroeconomic shock (variance = 1.0)
        - Factor 1: Debt service coverage shock (corr with macro = rho)
        - Factor 2: Collateral haircut shock (corr with macro = 0.5 * rho,
          corr with debt service = 0.75 * rho)

    Args:
        asset_correlation: Basel asset correlation parameter rho in [0.0, 1.0).

    Returns:
        3x3 symmetric positive-definite NumPy correlation matrix.

    Raises:
        SimulationConfigError: If rho is out of bounds [0.0, 1.0) or the matrix
            fails the Cholesky positive-definiteness check.
    """
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

    Execution Flow:
        1. Validates `pd` within [0.0, 1.0] and checks positive-definiteness of the
           correlation matrix (pre-computing the lower Cholesky factor `L`).
        2. Draws an `(N, 3)` matrix of independent standard normal innovations using
           a seed-pinned `np.random.default_rng(config.seed)` generator.
        3. Transforms innovations into correlated shock paths via `correlated = Z @ L^T`.
        4. Synthesizes correlated asset return paths blending systemic macro risk and
           idiosyncratic balance-sheet shocks.
        5. Evaluates default condition paths using compiled `scipy.special.ndtr` and `ndtri`
           ufuncs on the hot path for sub-5ms performance.
        6. Extracts the 10th, 50th, and 90th percentiles using Weibull interpolation.
        7. Returns an immutable, validated `PDBand` ensuring `P10 <= P50 <= P90`.

    Degenerate Boundary Conditions:
        - If `pd == 0.0`, returns trivial `P10 = P50 = P90 = 0.0`.
        - If `pd == 1.0`, returns trivial `P10 = P50 = P90 = 1.0`.

    Args:
        pd: Calibrated unconditional Probability of Default from Tier 1 in [0.0, 1.0].
        config: SimulationConfig object containing `n_iterations`, `seed`, `asset_correlation`,
            and numerical tolerances.
        correlation_matrix: Optional custom 3x3 correlation matrix. If None, builds the
            canonical matrix using `build_correlation_matrix(config.asset_correlation)`.

    Returns:
        Validated `PDBand` model with fields `p10`, `p50`, and `p90`.

    Raises:
        SimulationConfigError: If `pd` is out of bounds, or if the correlation
            matrix is malformed or non-positive-definite.
    """
    pd_value = float(pd)
    if not 0.0 <= pd_value <= 1.0:
        raise SimulationConfigError(f"pd must be within [0.0, 1.0]; got {pd_value!r}.")

    if correlation_matrix is None:
        matrix = build_correlation_matrix(config.asset_correlation)
        chol = linalg.cholesky(matrix, lower=True)
    else:
        matrix = np.asarray(correlation_matrix, dtype=float)
        if matrix.shape != (3, 3):
            raise SimulationConfigError(
                f"Correlation matrix must be 3x3; got shape {matrix.shape}."
            )
        try:
            chol = linalg.cholesky(matrix, lower=True)
        except linalg.LinAlgError as exc:
            raise SimulationConfigError("Correlation matrix must be positive definite.") from exc

    n_iterations = int(config.n_iterations)
    rng = np.random.default_rng(config.seed)
    innovations = rng.standard_normal((n_iterations, 3))
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
        alpha_paths = ndtr(asset_returns)
        transformed = (
            float(ndtri(pd_value)) + np.sqrt(rho) * ndtri(alpha_paths)
        ) / np.sqrt(1.0 - rho)
        default_band = np.percentile(
            ndtr(transformed), [10, 50, 90], method="weibull"
        )

    band = PDBand(
        p10=float(default_band[0]),
        p50=float(default_band[1]),
        p90=float(default_band[2]),
    )
    return band
