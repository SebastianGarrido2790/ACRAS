"""Tier 2 simulation package.

This package contains the analytical benchmark and downstream Monte Carlo engine used
for P10/P50/P90 default-probability validation.
"""

from src.tier2_simulation.benchmark import (
    vasicek_cdf,
    vasicek_pdf,
    vasicek_quantile,
    verify_simulation_benchmark,
)
from src.tier2_simulation.engine import SimulationConfigError, run_monte_carlo_simulation

__all__ = [
    "SimulationConfigError",
    "run_monte_carlo_simulation",
    "vasicek_cdf",
    "vasicek_pdf",
    "vasicek_quantile",
    "verify_simulation_benchmark",
]
