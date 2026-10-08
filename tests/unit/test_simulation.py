"""Comprehensive automated test suite for Tier 2 Monte Carlo engine and orchestration.

Governed by:
    INV-1 (ADR-001): Pure deterministic scoring; zero LLM output in calculations.
    INV-2 (ADR-002): Sole inter-tier contract via typed, immutable EvidenceBundle.
    ADR-028 (D-2.0): Simulation configuration & parameter bounds enforcement.
    ADR-029 (D-2.1): Vectorized Monte Carlo engine & percentile monotonicity.
    ADR-030 (D-2.2): Analytical Vasicek closed-form benchmark & tolerance gate.
    ADR-031 (D-2.3): In-memory Tier 1 / Tier 2 decoupled integration pattern.
    ADR-032 (D-2.4): EvidenceBundle schema v1 contract & PDBand enforcement.
    ADR-033 (D-2.5): Deterministic financial ratio extraction & zero-division safety.
    PRD FR3, FR5, FR11, FR12; Roadmap Tier 2 Exit Criteria.

This test module formalizes all falsifications performed during Stages 1–7
into permanent automated regression tests.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from pydantic import ValidationError
from scipy.stats import norm

from src.config.loader import SimulationConfig, load_params
from src.schemas import EvidenceBundle, PDBand
from src.tier2_simulation.benchmark import (
    vasicek_quantile,
    verify_simulation_benchmark,
)
from src.tier2_simulation.engine import run_monte_carlo_simulation
from src.tier2_simulation.ratios import compute_financial_ratios
from src.tier2_simulation.service import (
    InvalidTier1InputError,
    Tier2SimulationService,
    run_simulation_pipeline,
)


def _base_config() -> SimulationConfig:
    """Return a baseline SimulationConfig matching canonical hyperparameters."""
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


def _tier1_bundle(**overrides: object) -> EvidenceBundle:
    """Build a valid Tier 1 (v0) bundle with accounting-grade raw features."""
    kwargs: dict[str, object] = {
        "company_id": "COMP-T2-001",
        "raw_features": {
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
        "schema_version": "v0",
        "pd": 0.032,
        "credit_rating": "BB",
    }
    kwargs.update(overrides)
    return EvidenceBundle(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 1. Stage 1 Formalization: Simulation Configuration & Parameter Validation
# ---------------------------------------------------------------------------


def test_simulation_config_validation() -> None:
    """[Stage 1 Gate] Parameters parse cleanly; out-of-bounds inputs raise ValidationError."""
    # 1. Valid configuration loaded from params.yaml
    app_config = load_params()
    sim_cfg = app_config.simulation
    assert sim_cfg.n_iterations == 10_000
    assert sim_cfg.asset_correlation == 0.15
    assert sim_cfg.latency_budget_ms == 5.0

    # 2. Falsification: out-of-bounds asset_correlation (> 1.0)
    with pytest.raises(ValidationError):
        SimulationConfig(
            n_iterations=10_000,
            seed=42,
            asset_correlation=1.5,
            tolerance_p10=0.015,
            tolerance_p50=0.015,
            tolerance_p90=0.020,
            latency_budget_ms=5.0,
            macro_volatility=0.20,
            debt_service_shock_std=0.15,
            asset_haircut_std=0.10,
        )

    # 3. Falsification: negative n_iterations
    with pytest.raises(ValidationError):
        SimulationConfig(
            n_iterations=-100,
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

    # 4. Falsification: extra unauthorized field forbidden
    with pytest.raises(ValidationError):
        SimulationConfig(
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
            unauthorized_key=123,  # type: ignore[call-arg]
        )


# ---------------------------------------------------------------------------
# 2. Stage 2 Formalization: Vasicek Closed-Form Analytical Benchmark
# ---------------------------------------------------------------------------


def test_vasicek_closed_form_quantiles() -> None:
    """[Stage 2 Gate] Closed-form quantiles match exact mathematical theory."""
    p = 0.03
    rho = 0.15
    for alpha in (0.10, 0.50, 0.90):
        expected = float(
            norm.cdf(
                (norm.ppf(p) + math.sqrt(rho) * norm.ppf(alpha)) / math.sqrt(1.0 - rho)
            )
        )
        actual = vasicek_quantile(p=p, rho=rho, alpha=alpha)
        assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)


def test_benchmark_tolerance_checker_both_directions() -> None:
    """[Stage 2 Falsification] Tolerance gate passes exact band and rejects corruption."""
    p = 0.03
    rho = 0.15
    tolerances = {"p10": 0.015, "p50": 0.015, "p90": 0.020}

    # Pass direction: theoretical exact quantiles
    valid_band = {
        "p10": vasicek_quantile(p, rho, 0.10),
        "p50": vasicek_quantile(p, rho, 0.50),
        "p90": vasicek_quantile(p, rho, 0.90),
    }
    is_valid, metrics = verify_simulation_benchmark(valid_band, p, rho, tolerances)
    assert is_valid is True
    assert metrics["max_delta"] <= 1e-12

    # Block direction: deliberately corrupt p90 by +0.05 (violates 0.020 tolerance)
    corrupted_band = dict(valid_band)
    corrupted_band["p90"] = min(1.0, valid_band["p90"] + 0.05)
    is_valid_corr, metrics_corr = verify_simulation_benchmark(
        corrupted_band, p, rho, tolerances
    )
    assert is_valid_corr is False
    assert metrics_corr["p90_delta"] > 0.020


# ---------------------------------------------------------------------------
# 3. Stage 3 Formalization: Vectorized Monte Carlo Engine
# ---------------------------------------------------------------------------


def test_monte_carlo_engine_seed_reproducibility() -> None:
    """[Stage 3 Falsification 1] Identical seeds yield bit-for-bit identical outputs."""
    config = _base_config()
    first = run_monte_carlo_simulation(pd=0.032, config=config)
    second = run_monte_carlo_simulation(pd=0.032, config=config)
    assert first == second
    assert first.p10 == second.p10
    assert first.p50 == second.p50
    assert first.p90 == second.p90


def test_monte_carlo_percentile_monotonicity() -> None:
    """[Stage 3 Gate] Monotonicity 0.0 <= p10 <= p50 <= p90 <= 1.0 across 100 cases."""
    config = _base_config()
    rng = np.random.default_rng(2026)
    test_pds = rng.uniform(0.0005, 0.9995, size=98).tolist()
    # Explicitly test boundary values
    test_pds.extend([0.0, 1.0])

    for pd_val in test_pds:
        band = run_monte_carlo_simulation(pd=pd_val, config=config)
        assert 0.0 <= band.p10 <= band.p50 <= band.p90 <= 1.0
        if pd_val == 0.0:
            assert band.p10 == 0.0 and band.p50 == 0.0 and band.p90 == 0.0
        elif pd_val == 1.0:
            assert band.p10 == 1.0 and band.p50 == 1.0 and band.p90 == 1.0


# ---------------------------------------------------------------------------
# 4. Stage 4 Formalization: Domain Financial Ratios Extraction
# ---------------------------------------------------------------------------


def test_financial_ratios_extraction() -> None:
    """[Stage 4 Gate & Falsification] 7 ratios compute accurately; zero division clamps."""
    # 1. Standard financial inputs
    standard_features = {
        "current_assets": 200_000.0,
        "current_liabilities": 100_000.0,
        "quick_assets": 120_000.0,
        "total_debt": 150_000.0,
        "total_equity": 300_000.0,
        "net_income": 40_000.0,
        "total_revenue": 500_000.0,
        "operating_profit": 75_000.0,
        "ebit": 60_000.0,
        "interest_expense": 15_000.0,
        "total_assets": 450_000.0,
    }
    ratios = compute_financial_ratios(standard_features)
    assert ratios["current_ratio"] == pytest.approx(2.0)
    assert ratios["quick_ratio"] == pytest.approx(1.2)
    assert ratios["debt_to_equity"] == pytest.approx(0.5)
    assert ratios["net_profit_margin"] == pytest.approx(0.08)
    assert ratios["ebitda_margin"] == pytest.approx(0.15)
    assert ratios["interest_coverage"] == pytest.approx(4.0)
    assert ratios["asset_turnover"] == pytest.approx(500_000.0 / 450_000.0)
    assert all(math.isfinite(val) for val in ratios.values())

    # 2. Zero-denominator edge cases (defensive clamping)
    zero_denom_features = {
        "current_assets": 100_000.0,
        "current_liabilities": 0.0,
        "quick_assets": 50_000.0,
        "total_debt": 20_000.0,
        "total_equity": 0.0,
        "net_income": 10_000.0,
        "total_revenue": 0.0,
        "operating_profit": 5_000.0,
        "ebit": 10_000.0,
        "interest_expense": 0.0,
        "total_assets": 0.0,
    }
    safe_ratios = compute_financial_ratios(zero_denom_features)
    assert safe_ratios["current_ratio"] == 999.0
    assert safe_ratios["quick_ratio"] == 999.0
    assert safe_ratios["debt_to_equity"] == 999.0
    assert safe_ratios["interest_coverage"] == 999.0
    assert all(math.isfinite(val) for val in safe_ratios.values())


# ---------------------------------------------------------------------------
# 5. Stage 5 Formalization: EvidenceBundle Schema v1 Contract
# ---------------------------------------------------------------------------


def test_evidence_bundle_v1_contract() -> None:
    """[Stage 5 Gate & Falsification] v1 strictly enforces Tier 1 and Tier 2 outputs."""
    valid_kwargs: dict[str, object] = {
        "company_id": "COMP-V1-001",
        "raw_features": {"leverage": 0.4},
        "schema_version": "v1",
        "pd": 0.025,
        "credit_rating": "BBB",
        "pd_band": PDBand(p10=0.015, p50=0.025, p90=0.050),
        "financial_ratios": {"current_ratio": 1.8},
    }
    # Pass direction
    bundle = EvidenceBundle(**valid_kwargs)  # type: ignore[arg-type]
    assert bundle.schema_version == "v1"
    assert bundle.pd_band is not None
    assert bundle.financial_ratios is not None
    assert bundle.persona_verdicts is None

    # Falsification 1: missing pd_band raises ValidationError
    missing_band = dict(valid_kwargs, pd_band=None)
    with pytest.raises(ValidationError):
        EvidenceBundle(**missing_band)  # type: ignore[arg-type]

    # Falsification 2: invalid credit_rating raises ValidationError
    bad_rating = dict(valid_kwargs, credit_rating="INVALID")
    with pytest.raises(ValidationError):
        EvidenceBundle(**bad_rating)  # type: ignore[arg-type]

    # Falsification 3: empty financial_ratios raises ValidationError
    empty_ratios = dict(valid_kwargs, financial_ratios={})
    with pytest.raises(ValidationError):
        EvidenceBundle(**empty_ratios)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 6. Stage 6 Formalization: Tier 1/2 In-Memory Orchestration Service
# ---------------------------------------------------------------------------


def test_tier2_service_end_to_end() -> None:
    """[Stage 6 Gate] Tier 1 bundle -> valid v1 bundle with band and ratios."""
    service = Tier2SimulationService(_base_config())
    input_bundle = _tier1_bundle()
    result = service.run(input_bundle)

    assert result.schema_version == "v1"
    assert result.company_id == "COMP-T2-001"
    assert result.pd == pytest.approx(0.032)
    assert result.credit_rating == "BB"
    assert result.pd_band is not None
    assert result.pd_band.p10 <= result.pd_band.p50 <= result.pd_band.p90
    assert result.financial_ratios is not None
    assert result.financial_ratios["current_ratio"] == pytest.approx(2.0)
    assert result.financial_ratios["interest_coverage"] == pytest.approx(5.0)
    assert result.persona_verdicts is None


def test_tier2_service_functional_runner_matches_service() -> None:
    """Functional runner and service class produce identical outputs."""
    config = _base_config()
    bundle = _tier1_bundle()
    via_function = run_simulation_pipeline(bundle, config)
    via_service = Tier2SimulationService(config).run(bundle)
    assert via_function == via_service


def test_tier2_service_seed_reproducibility() -> None:
    """Service runs are bit-for-bit reproducible for identical seeds."""
    config = _base_config()
    first = run_simulation_pipeline(_tier1_bundle(), config)
    second = run_simulation_pipeline(_tier1_bundle(), config)
    assert first == second


def test_tier2_service_falsification_missing_pd() -> None:
    """[Stage 6 Falsification] Missing pd halts before matrix calculations."""
    bundle = _tier1_bundle(pd=None)
    with pytest.raises(InvalidTier1InputError, match="pd"):
        run_simulation_pipeline(bundle, _base_config())


def test_tier2_service_falsification_empty_raw_features() -> None:
    """[Stage 6 Falsification] Empty raw_features halts before matrix calculations."""
    bundle = _tier1_bundle(raw_features={})
    with pytest.raises(InvalidTier1InputError, match="raw_features"):
        run_simulation_pipeline(bundle, _base_config())


def test_tier2_service_falsification_invalid_rating() -> None:
    """[Stage 6 Falsification] Unrecognized credit rating halts with domain error."""
    bundle = _tier1_bundle(credit_rating="NOT-A-RATING")
    with pytest.raises(InvalidTier1InputError, match="credit_rating"):
        run_simulation_pipeline(bundle, _base_config())
