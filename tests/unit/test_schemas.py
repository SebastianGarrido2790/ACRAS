"""Unit tests and adversarial falsification for Evidence Bundle schemas.

Governed by:
    INV-2 (ADR-002): Sole inter-tier contract.
    INV-4 (ADR-004): Structured PersonaVerdict contract.
    ADR-014: Pre-v0 draft skeleton and strict rejection falsification.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schemas import EvidenceBundle, PDBand, PersonaVerdict


def test_evidence_bundle_pre_v0_smoke_instantiation() -> None:
    """[GATE 6 Smoke Test] Instantiation with only Phase 0 populated fields.

    Verifies:
    1. Schema initializes cleanly with company_id and raw_features.
    2. schema_version defaults to 'pre-v0-draft'.
    3. All downstream Tier 1–3 placeholders default to None.
    4. Sub-models (PDBand, PersonaVerdict) are importable and functional.
    """
    raw_sample = {
        " ROA(A) before interest and % after tax": 0.42,
        " Operating Gross Margin": 0.60,
        " Debt ratio %": 0.20,
    }

    bundle = EvidenceBundle(
        company_id="COMP-001",
        raw_features=raw_sample,
        schema_version="pre-v0-draft",
    )

    assert bundle.company_id == "COMP-001"
    assert bundle.schema_version == "pre-v0-draft"
    assert bundle.raw_features == raw_sample

    # Downstream placeholders must be None
    assert bundle.pd is None
    assert bundle.credit_rating is None
    assert bundle.pd_band is None
    assert bundle.financial_ratios is None
    assert bundle.persona_verdicts is None


def test_evidence_bundle_full_tier_structure_simulation() -> None:
    """Verifies that future downstream tiers can cleanly populate their typed fields."""
    band = PDBand(p10=0.03, p50=0.07, p90=0.15)
    cro_verdict = PersonaVerdict(
        persona="cro",
        recommendation="conditional",
        lean=-0.3,
        confidence=0.85,
        rationale="Elevated leverage requires covenant guarantees.",
    )

    bundle = EvidenceBundle(
        company_id="COMP-002",
        raw_features={"Debt ratio %": 0.35},
        schema_version="v1",
        pd=0.072,
        credit_rating="BBB",
        pd_band=band,
        financial_ratios={"leverage": 2.1},
        persona_verdicts={"cro": cro_verdict},
    )

    assert bundle.pd == 0.072
    assert bundle.credit_rating == "BBB"
    assert bundle.pd_band is not None
    assert bundle.pd_band.p50 == 0.07
    assert bundle.persona_verdicts is not None
    assert bundle.persona_verdicts["cro"].persona == "cro"


def test_evidence_bundle_falsification_missing_required_fields() -> None:
    """[GATE 6 Falsification] Omission of required Phase 0 fields raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        # Omitting raw_features
        EvidenceBundle(company_id="COMP-003")  # type: ignore[call-arg]
    assert "raw_features" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        # Omitting company_id
        EvidenceBundle(raw_features={})  # type: ignore[call-arg]
    assert "company_id" in str(exc_info.value)


def test_evidence_bundle_falsification_invalid_types_and_bounds() -> None:
    """[GATE 6 Falsification] Invalid types or out-of-bound values raise ValidationError."""
    # 1. Invalid pd type (string instead of float)
    with pytest.raises(ValidationError):
        EvidenceBundle(
            company_id="COMP-004",
            raw_features={},
            pd="invalid-pd-string",  # type: ignore[arg-type]
        )

    # 2. Out-of-bounds pd (> 1.0)
    with pytest.raises(ValidationError):
        EvidenceBundle(
            company_id="COMP-004",
            raw_features={},
            pd=1.5,
        )

    # 3. Monotonicity violation in PDBand (p10 > p50)
    with pytest.raises(ValidationError):
        PDBand(p10=0.50, p50=0.10, p90=0.80)

    # 4. Invalid persona name in PersonaVerdict (violates INV-8)
    with pytest.raises(ValidationError):
        PersonaVerdict(
            persona="auditor",  # type: ignore[arg-type]
            recommendation="approve",
            lean=0.0,
            confidence=0.9,
            rationale="Valid rationale text exceeding 10 characters.",
        )

    # 5. Invalid recommendation category
    with pytest.raises(ValidationError):
        PersonaVerdict(
            persona="cro",
            recommendation="maybe",  # type: ignore[arg-type]
            lean=0.0,
            confidence=0.9,
            rationale="Valid rationale text exceeding 10 characters.",
        )


def test_evidence_bundle_falsification_extra_fields_forbidden() -> None:
    """[GATE 6 Falsification] Extra unauthorized fields are strictly forbidden (INV-2)."""
    with pytest.raises(ValidationError) as exc_info:
        EvidenceBundle(
            company_id="COMP-005",
            raw_features={},
            unauthorized_ad_hoc_context="leaked_data",  # type: ignore[call-arg]
        )
    assert "extra_forbidden" in str(exc_info.value)


def test_evidence_bundle_immutability() -> None:
    """[GATE 6 Falsification] Evidence bundle is frozen and immutable."""
    bundle = EvidenceBundle(
        company_id="COMP-006", raw_features={}, schema_version="pre-v0-draft"
    )
    with pytest.raises(ValidationError):
        bundle.company_id = "NEW_ID"  # type: ignore[misc]


def _valid_v1_kwargs() -> dict[str, object]:
    """Baseline valid v1 payload for Stage 5 contract tests."""
    return {
        "company_id": "COMP-V1",
        "raw_features": {"Debt ratio %": 0.35},
        "schema_version": "v1",
        "pd": 0.032,
        "credit_rating": "BB",
        "pd_band": PDBand(p10=0.02, p50=0.032, p90=0.06),
        "financial_ratios": {"current_ratio": 1.5, "debt_to_equity": 0.8},
    }


def test_evidence_bundle_v1_valid_contract() -> None:
    """[Stage 5 Gate] A complete Tier 1 + Tier 2 payload validates as v1."""
    bundle = EvidenceBundle(**_valid_v1_kwargs())  # type: ignore[arg-type]
    assert bundle.schema_version == "v1"
    assert bundle.pd_band is not None
    assert bundle.financial_ratios is not None
    # Tier 3 stays decoupled: persona_verdicts=None is valid for v1.
    assert bundle.persona_verdicts is None


def test_evidence_bundle_v1_falsification_missing_pd_band() -> None:
    """[Stage 5 Falsification 1] v1 with pd_band=None raises ValidationError."""
    kwargs = _valid_v1_kwargs()
    kwargs["pd_band"] = None
    with pytest.raises(ValidationError) as exc_info:
        EvidenceBundle(**kwargs)  # type: ignore[arg-type]
    assert "pd_band" in str(exc_info.value)


def test_evidence_bundle_v1_falsification_inverted_monotonicity() -> None:
    """[Stage 5 Falsification 2] Inverted percentiles raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        PDBand(p10=0.05, p50=0.02, p90=0.10)
    assert "p10 <= p50 <= p90" in str(exc_info.value)


def test_evidence_bundle_v1_falsification_invalid_rating_and_ratios() -> None:
    """[Stage 5] v1 rejects unknown ratings and empty/non-finite ratio maps."""
    base = _valid_v1_kwargs()

    invalid_rating = dict(base)
    invalid_rating["credit_rating"] = "NOT-A-RATING"
    with pytest.raises(ValidationError):
        EvidenceBundle(**invalid_rating)  # type: ignore[arg-type]

    empty_ratios = dict(base)
    empty_ratios["financial_ratios"] = {}
    with pytest.raises(ValidationError):
        EvidenceBundle(**empty_ratios)  # type: ignore[arg-type]

    non_finite_ratios = dict(base)
    non_finite_ratios["financial_ratios"] = {"current_ratio": float("nan")}
    with pytest.raises(ValidationError):
        EvidenceBundle(**non_finite_ratios)  # type: ignore[arg-type]
