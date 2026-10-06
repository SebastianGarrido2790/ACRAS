"""Performance benchmark and latency regression gate for the Tier 2 simulation engine.

Governed by:
    D-2.6: Performance Profiling & Latency Regression Gate.
    Roadmap Exit Criteria (Tier 2): Vectorized Monte Carlo runtime stays strictly
        under the 5.0 ms budget at N=10,000 iterations.
    INV-1 (ADR-001): Pure deterministic scoring executed within tight SLA budgets.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest

from src.config.loader import SimulationConfig, load_params
from src.schemas import EvidenceBundle
from src.tier2_simulation.engine import run_monte_carlo_simulation
from src.tier2_simulation.service import Tier2SimulationService

logger = logging.getLogger(__name__)


def _load_simulation_config() -> SimulationConfig:
    """Load canonical simulation hyperparameters from params.yaml."""
    return load_params().simulation


def measure_latencies_ms(
    run_fn: Callable[[], Any],
    *,
    n_warmup: int = 10,
    n_runs: int = 100,
) -> dict[str, float]:
    """Measure execution latencies over warm-up and timed runs in milliseconds.

    Args:
        run_fn: Callable executing a single simulation run.
        n_warmup: Number of un-timed warm-up iterations to stabilize BLAS threads.
        n_runs: Number of timed iterations.

    Returns:
        Dictionary containing summary latency metrics in milliseconds:
        p50, p90, p95, min, max, mean.
    """
    for _ in range(n_warmup):
        run_fn()

    latencies_ms: list[float] = []
    for _ in range(n_runs):
        start_ns = time.perf_counter_ns()
        run_fn()
        elapsed_ns = time.perf_counter_ns() - start_ns
        latencies_ms.append(elapsed_ns / 1_000_000.0)

    arr = np.asarray(latencies_ms, dtype=float)
    return {
        "n_runs": float(n_runs),
        "min": float(np.min(arr)),
        "mean": float(np.mean(arr)),
        "p50": float(np.percentile(arr, 50)),
        "p90": float(np.percentile(arr, 90)),
        "p95": float(np.percentile(arr, 95)),
        "max": float(np.max(arr)),
    }


def assert_latency_budget(metrics: dict[str, float], budget_ms: float = 5.0) -> None:
    """Enforce the hard P95 latency SLA gate.

    Raises:
        AssertionError: If P95 latency is greater than or equal to budget_ms.
    """
    p95 = metrics["p95"]
    p50 = metrics["p50"]
    p90 = metrics["p90"]
    if p95 >= budget_ms:
        raise AssertionError(
            f"Execution exceeded the {budget_ms:.1f}ms latency threshold: "
            f"P95={p95:.3f}ms (budget={budget_ms:.1f}ms, P50={p50:.3f}ms, P90={p90:.3f}ms)."
        )


def test_vectorized_monte_carlo_engine_latency_gate(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """[Gate 7] Vectorized engine P95 latency must be strictly < 5.0ms at N=10,000."""
    config = _load_simulation_config()
    assert config.n_iterations == 10_000
    assert config.latency_budget_ms == 5.0

    def run_engine() -> None:
        run_monte_carlo_simulation(pd=0.032, config=config)

    metrics = measure_latencies_ms(run_engine, n_warmup=10, n_runs=100)

    summary = (
        f"[PERF BENCHMARK - Core Engine] N={config.n_iterations} iterations, 100 runs: "
        f"P50={metrics['p50']:.3f}ms, P90={metrics['p90']:.3f}ms, P95={metrics['p95']:.3f}ms, "
        f"min={metrics['min']:.3f}ms, max={metrics['max']:.3f}ms "
        f"(budget={config.latency_budget_ms:.1f}ms)"
    )
    print(summary)
    logger.info(summary)

    assert_latency_budget(metrics, budget_ms=config.latency_budget_ms)
    assert metrics["p95"] < 5.0


def test_tier2_in_memory_service_latency_gate(capsys: pytest.CaptureFixture[str]) -> None:
    """[Gate 7] Full in-memory service (bundle in -> bundle out) must stay < 5.0ms."""
    config = _load_simulation_config()
    service = Tier2SimulationService(config)

    bundle = EvidenceBundle(
        company_id="COMP-BENCH-001",
        raw_features={
            "current_assets": 500_000.0,
            "current_liabilities": 250_000.0,
            "quick_assets": 300_000.0,
            "total_debt": 400_000.0,
            "total_equity": 600_000.0,
            "net_income": 80_000.0,
            "total_revenue": 1_000_000.0,
            "operating_profit": 150_000.0,
            "ebit": 150_000.0,
            "interest_expense": 30_000.0,
            "total_assets": 1_200_000.0,
        },
        schema_version="v0",
        pd=0.032,
        credit_rating="BB",
    )

    def run_pipeline() -> None:
        service.run(bundle)

    metrics = measure_latencies_ms(run_pipeline, n_warmup=10, n_runs=100)

    summary = (
        f"[PERF BENCHMARK - Full Pipeline] N={config.n_iterations} iterations, 100 runs: "
        f"P50={metrics['p50']:.3f}ms, P90={metrics['p90']:.3f}ms, P95={metrics['p95']:.3f}ms, "
        f"budget={config.latency_budget_ms:.1f}ms"
    )
    print(summary)
    logger.info(summary)

    assert_latency_budget(metrics, budget_ms=config.latency_budget_ms)
    assert metrics["p95"] < 5.0


def test_falsification_unvectorized_slow_loop_triggers_gate_failure() -> None:
    """[Gate 7 Falsification] Deliberate unvectorized Python loop provably fails gate."""

    def mock_unvectorized_simulation() -> list[float]:
        """Deliberate slow simulation path using an unvectorized Python loop."""
        paths: list[float] = []
        for i in range(10_000):
            z1 = math.sin(float(i))
            z2 = math.cos(float(i))
            z3 = math.tan(float(i % 100) + 0.1)
            paths.append(0.15 * z1 + 0.85 * (z2 + z3))
        paths.sort()
        return paths

    # Measure over 15 runs to verify P95 latency exceeds 5.0ms
    metrics = measure_latencies_ms(mock_unvectorized_simulation, n_warmup=3, n_runs=15)

    assert metrics["p95"] > 5.0, (
        f"Expected slow mock path to exceed 5.0ms, got P95={metrics['p95']:.3f}ms"
    )

    with pytest.raises(AssertionError, match="exceeded the 5.0ms latency threshold"):
        assert_latency_budget(metrics, budget_ms=5.0)
