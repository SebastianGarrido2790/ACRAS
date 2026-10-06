"""Tier 2 orchestration tests: service contract and Stage 6 falsification.

Governed by:
    D-2.3 (ADR-031): In-memory Tier 1/Tier 2 integration; malformed Tier 1 inputs
        halt with `InvalidTier1InputError` before any matrix operations.
    D-2.4 (ADR-032): Pipeline output is a valid v1 `EvidenceBundle`.
"""

from __future__ import annotations

import pytest

from src.config.loader import SimulationConfig
from src.schemas import EvidenceBundle
from src.tier2_simulation.service import (
    InvalidTier1InputError,
    Tier2SimulationService,
    run_simulation_pipeline,
)


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


def _tier1_bundle(**overrides: object) -> EvidenceBundle:
    """Build a Tier 1 (v0) bundle with accounting-grade raw features."""
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


def test_tier2_service_end_to_end() -> None:
    """[Stage 6 Gate] Tier 1 bundle -> valid v1 bundle with band + ratios."""
    service = Tier2SimulationService(_base_config())
    result = service.run(_tier1_bundle())

    assert result.schema_version == "v1"
    assert result.company_id == "COMP-T2-001"
    assert result.pd == pytest.approx(0.032)
    assert result.credit_rating == "BB"
    assert result.pd_band is not None
    assert result.pd_band.p10 <= result.pd_band.p50 <= result.pd_band.p90
    assert result.financial_ratios is not None
    assert result.financial_ratios["current_ratio"] == pytest.approx(2.0)
    assert result.financial_ratios["interest_coverage"] == pytest.approx(5.0)
    # Tier boundary: no Tier 3 verdicts leak into a fresh Tier 2 output.
    assert result.persona_verdicts is None
    # Input bundle is untouched (frozen, new object returned).
    assert result is not _tier1_bundle()


def test_tier2_service_functional_runner_matches_service() -> None:
    """Functional runner and service class agree on identical inputs."""
    config = _base_config()
    bundle = _tier1_bundle()
    via_function = run_simulation_pipeline(bundle, config)
    via_service = Tier2SimulationService(config).run(bundle)
    assert via_function == via_service


def test_tier2_service_seed_reproducibility() -> None:
    """Identical seeds yield identical enriched bundles."""
    config = _base_config()
    first = run_simulation_pipeline(_tier1_bundle(), config)
    second = run_simulation_pipeline(_tier1_bundle(), config)
    assert first == second


def test_tier2_service_falsification_missing_pd() -> None:
    """[Stage 6 Falsification] Missing `pd` halts with domain error pre-matrix."""
    bundle = _tier1_bundle(pd=None)
    with pytest.raises(InvalidTier1InputError, match="pd"):
        run_simulation_pipeline(bundle, _base_config())


def test_tier2_service_falsification_empty_raw_features() -> None:
    """[Stage 6 Falsification] Empty `raw_features` halts with domain error."""
    bundle = _tier1_bundle(raw_features={})
    with pytest.raises(InvalidTier1InputError, match="raw_features"):
        run_simulation_pipeline(bundle, _base_config())


def test_tier2_service_falsification_invalid_rating() -> None:
    """[Stage 6 Falsification] Unrecognized rating halts with domain error."""
    bundle = _tier1_bundle(credit_rating="NOT-A-RATING")
    with pytest.raises(InvalidTier1InputError, match="credit_rating"):
        run_simulation_pipeline(bundle, _base_config())
