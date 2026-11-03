"""Contract tests for the additive Tier 3 evidence fields (P4-01 / ADR-016).

Covers `spec.md` §6 acceptance criterion 1 and T3-FR-01 … T3-FR-04:
the four optional fields preserve `None`, `PersonaVerdict.limitations`
round-trips, unknown fields stay rejected, v1 is unchanged, and `p90_pd`
remains computed from `pd_band.p90`.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schemas.evidence_bundle import EvidenceBundle, PDBand, PersonaVerdict

PROFILE: dict[str, float] = {
    "current_assets": 500000.0,
    "current_liabilities": 250000.0,
    "quick_assets": 300000.0,
    "total_debt": 400000.0,
    "total_equity": 600000.0,
    "net_income": 80000.0,
    "total_revenue": 1000000.0,
    "operating_profit": 150000.0,
    "ebit": 150000.0,
    "interest_expense": 30000.0,
    "total_assets": 1200000.0,
}


PROVENANCE: dict[str, str] = {
    "financial_ratios": "derived",
    "p90_pd": "derived",
    "covenant_flags": "synthetic",
    "revenue_growth_rate": "synthetic",
    "pipeline_value_estimate": "synthetic",
    "concentration_flag": "synthetic",
}

ASSUMPTIONS: dict[str, str] = {
    "covenant_flags": "supplied profile flags; not observed",
    "revenue_growth_rate": "assumed from profile; not observed",
    "pipeline_value_estimate": "deal-level synthetic",
    "concentration_flag": "assumed from profile; not observed",
}


def _v2_kwargs() -> dict[str, object]:
    """Return a minimal valid v2 bundle with the four Tier 3 fields absent."""
    return {
        "company_id": "COMP-CONTRACT-01",
        "raw_features": {"leverage": 0.4},
        "schema_version": "v2",
        "accounting_profile": PROFILE,
        "pd": 0.032,
        "credit_rating": "BB",
        "pd_band": PDBand(p10=0.015, p50=0.032, p90=0.05),
        "provenance": dict(PROVENANCE),
        "synthetic_assumptions": dict(ASSUMPTIONS),
    }


def _v1_kwargs() -> dict[str, object]:
    return {
        "company_id": "COMP-CONTRACT-V1",
        "raw_features": {"leverage": 0.4},
        "schema_version": "v1",
        "pd": 0.032,
        "credit_rating": "BB",
        "pd_band": PDBand(p10=0.015, p50=0.032, p90=0.05),
        "financial_ratios": {"current_ratio": 2.0},
    }


def test_four_fields_round_trip_when_present() -> None:
    """T3-FR-01: populated values are typed and retained exactly."""
    bundle = EvidenceBundle(  # type: ignore[arg-type]
        **{
            **_v2_kwargs(),
            "covenant_flags": ["no_material_breach"],
            "revenue_growth_rate": 0.12,
            "pipeline_value_estimate": 250000.0,
            "concentration_flag": False,
        }
    )
    assert bundle.covenant_flags == ["no_material_breach"]
    assert bundle.revenue_growth_rate == 0.12
    assert bundle.pipeline_value_estimate == 250000.0
    assert bundle.concentration_flag is False


def test_absent_fields_preserve_none() -> None:
    """T3-FR-01 / D-01: absence stays `None`, never `0.0`, `[]`, or `False`."""
    bundle = EvidenceBundle(**_v2_kwargs())  # type: ignore[arg-type]
    assert bundle.covenant_flags is None
    assert bundle.revenue_growth_rate is None
    assert bundle.pipeline_value_estimate is None
    assert bundle.concentration_flag is None
    # Prove distinctness from the forbidden coerced defaults, not just falsiness.
    assert bundle.covenant_flags != []
    assert bundle.revenue_growth_rate != 0.0
    assert bundle.pipeline_value_estimate != 0.0
    assert bundle.concentration_flag is not False


def test_limitations_defaults_empty_and_round_trips() -> None:
    """T3-FR-03: `limitations` defaults to empty and retains entries."""
    default = PersonaVerdict(
        persona="cro",
        recommendation="conditional",
        lean=-0.2,
        confidence=0.5,
        rationale="Covenant history unavailable; conditional pending review.",
    )
    assert default.limitations == []

    populated = PersonaVerdict(
        persona="growth",
        recommendation="conditional",
        lean=0.1,
        confidence=0.4,
        rationale="Revenue growth unavailable; cannot underwrite the growth case.",
        limitations=["revenue_growth_rate unavailable", "pipeline_value_estimate unavailable"],
    )
    restored = PersonaVerdict.model_validate_json(populated.model_dump_json())
    assert restored.limitations == [
        "revenue_growth_rate unavailable",
        "pipeline_value_estimate unavailable",
    ]


def test_unknown_fields_still_rejected() -> None:
    """T3-FR-04: `extra="forbid"` is unchanged by the additive fields."""
    for unknown in (
        "tail_loss_estimate",
        "capital_consumption_estimate",
        "persona_summary",
    ):
        with pytest.raises(ValidationError):
            EvidenceBundle(**{**_v2_kwargs(), unknown: 1.0})  # type: ignore[arg-type]


def test_v2_bundle_is_frozen() -> None:
    """T3-FR-04: `frozen=True` is unchanged."""
    bundle = EvidenceBundle(**_v2_kwargs())  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        bundle.pd = 0.5  # type: ignore[misc]


def test_v1_contract_unchanged_and_ignores_tier3_fields() -> None:
    """T3-FR-04: v1 validation still works without the four fields."""
    bundle = EvidenceBundle(**_v1_kwargs())  # type: ignore[arg-type]
    assert bundle.schema_version == "v1"
    assert bundle.covenant_flags is None
    assert bundle.revenue_growth_rate is None
    assert bundle.pipeline_value_estimate is None
    assert bundle.concentration_flag is None
    assert bundle.persona_verdicts is None


def test_p90_pd_remains_computed_for_v1_and_v2() -> None:
    """T3-FR-04: `p90_pd` stays bound to `pd_band.p90`."""
    v2 = EvidenceBundle(**_v2_kwargs())  # type: ignore[arg-type]
    v1 = EvidenceBundle(**_v1_kwargs())  # type: ignore[arg-type]
    assert v2.pd_band is not None and v2.p90_pd == v2.pd_band.p90
    assert v1.pd_band is not None and v1.p90_pd == v1.pd_band.p90


def test_derived_limited_to_defined_derivations() -> None:
    """T3-FR-02: `derived` outside `financial_ratios`/`p90_pd` is rejected."""
    kwargs = _v2_kwargs()
    kwargs["provenance"] = {**PROVENANCE, "revenue_growth_rate": "derived"}
    with pytest.raises(ValueError, match="derived"):
        EvidenceBundle(**kwargs)  # type: ignore[arg-type]


def test_every_synthetic_tag_needs_an_assumption() -> None:
    """T3-FR-02: including the newly typed `concentration_flag`."""
    kwargs = _v2_kwargs()
    kwargs["synthetic_assumptions"] = {
        key: value for key, value in ASSUMPTIONS.items() if key != "concentration_flag"
    }
    with pytest.raises(ValueError, match="concentration_flag"):
        EvidenceBundle(**kwargs)  # type: ignore[arg-type]
