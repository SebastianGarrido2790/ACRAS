"""Tier 1 / Tier 2 in-memory orchestration service.

Governed by:
    D-2.3 (ADR-031): Tier 1/Tier 2 In-Memory Decoupled Integration Pattern.
        Tier 2 consumes Tier 1 output via a direct in-memory service — never over
        HTTP (rejected: +5–15 ms overhead breaks the sub-5 ms budget) and never by
        subclassing model internals (rejected: violates ADR-010 retraining boundary).
    INV-1 (ADR-001): Pure deterministic scoring; zero LLM output in calculations.
    INV-2 (ADR-002): The versioned EvidenceBundle is the sole inter-tier channel.
    D-2.4 (ADR-032): Returned bundles advance to `schema_version = "v1"`.

This module performs zero network calls and holds zero training/retraining
dependencies: it orchestrates only the pure engine (`engine.py`), the
deterministic ratio extractor (`ratios.py`), and the typed schema contract.
"""

from __future__ import annotations

import math

from src.config.loader import SimulationConfig
from src.schemas.evidence_bundle import VALID_CREDIT_RATINGS, EvidenceBundle
from src.tier2_simulation.engine import run_monte_carlo_simulation
from src.tier2_simulation.ratios import compute_financial_ratios

__all__ = [
    "InvalidTier1InputError",
    "Tier2SimulationService",
    "run_simulation_pipeline",
]


class InvalidTier1InputError(ValueError):
    """Raised when an input bundle lacks valid Tier 1 outputs.

    Halts the pipeline before any matrix operations when `pd` is missing or
    out of bounds, `credit_rating` is missing or unrecognized, or
    `raw_features` is empty.
    """


def _validate_tier1_inputs(bundle: EvidenceBundle) -> tuple[float, str]:
    """Check Tier 1 fields before any simulation work; return `(pd, rating)`.

    Raises:
        InvalidTier1InputError: If any required Tier 1 input is missing/invalid.
    """
    if bundle.pd is None or not math.isfinite(bundle.pd):
        raise InvalidTier1InputError(
            f"Tier 1 `pd` must be a finite value in [0.0, 1.0]; got {bundle.pd!r}."
        )
    if not 0.0 <= bundle.pd <= 1.0:
        raise InvalidTier1InputError(
            f"Tier 1 `pd` must be within [0.0, 1.0]; got {bundle.pd!r}."
        )
    if bundle.credit_rating is None or bundle.credit_rating not in VALID_CREDIT_RATINGS:
        raise InvalidTier1InputError(
            "Tier 1 `credit_rating` must be one of "
            f"{sorted(VALID_CREDIT_RATINGS)}; got {bundle.credit_rating!r}."
        )
    if not bundle.raw_features:
        raise InvalidTier1InputError(
            "Tier 1 `raw_features` must be a non-empty mapping for ratio extraction."
        )
    return bundle.pd, bundle.credit_rating


def run_simulation_pipeline(
    bundle: EvidenceBundle, config: SimulationConfig
) -> EvidenceBundle:
    """Enrich a Tier 1 bundle with Tier 2 outputs and return a new v1 bundle.

    Pure, deterministic, in-memory orchestration: validates Tier 1 inputs first
    (halting on `InvalidTier1InputError` before any matrix work), then runs the
    vectorized Monte Carlo engine and the deterministic ratio extractor.

    Args:
        bundle: Input bundle with Tier 1 `pd`, `credit_rating`, `raw_features`.
        config: Validated simulation hyperparameters.

    Returns:
        A new immutable `EvidenceBundle` with `schema_version="v1"`, `pd_band`,
        and `financial_ratios` populated. `persona_verdicts` is reset to `None`:
        any prior Tier 3 verdict was interpreted against older inputs and must
        not silently survive a Tier 2 re-run.

    Raises:
        InvalidTier1InputError: If Tier 1 inputs are missing or invalid.
        SimulationConfigError: If the engine configuration/correlation is invalid.
    """
    pd_value, credit_rating = _validate_tier1_inputs(bundle)

    pd_band = run_monte_carlo_simulation(pd_value, config)
    financial_ratios = compute_financial_ratios(dict(bundle.raw_features))

    return EvidenceBundle(
        company_id=bundle.company_id,
        raw_features=dict(bundle.raw_features),
        schema_version="v1",
        pd=pd_value,
        credit_rating=credit_rating,
        pd_band=pd_band,
        financial_ratios=financial_ratios,
        persona_verdicts=None,
    )


class Tier2SimulationService:
    """Stateful in-memory service wrapping `run_simulation_pipeline`.

    Binds one validated `SimulationConfig` at construction so callers submit
    only the Tier 1 bundle per request. No network, no model internals.
    """

    def __init__(self, config: SimulationConfig) -> None:
        """Bind the simulation configuration for subsequent runs."""
        self.config = config

    def run(self, bundle: EvidenceBundle) -> EvidenceBundle:
        """Execute the Tier 1 -> Tier 2 enrichment pipeline (see `run_simulation_pipeline`)."""
        return run_simulation_pipeline(bundle, self.config)
