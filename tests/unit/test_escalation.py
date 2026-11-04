"""Exhaustive escalation tests (P4-03 / T3-FR-13/14).

Covers every row of `spec.md` §4, the fixed precedence
(`incomplete` > `escalate` > `success`), stable reason codes, threshold
boundary semantics, and the guarantee that no outcome implies approval.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from src.agents.orchestration.divergence import compute_divergence
from src.agents.orchestration.escalation import (
    EscalationInputs,
    EscalationReason,
    EscalationResult,
    PersonaFailure,
    PersonaFailureReason,
    Tier3Status,
    evaluate_escalation,
)
from src.agents.orchestration.tier1_confidence import compute_tier1_confidence
from src.config.loader import load_params
from src.schemas.evidence_bundle import EvidenceBundle, PersonaVerdict

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def _verdict(persona: str, recommendation: str = "approve") -> PersonaVerdict:
    """Build a valid verdict for an escalation input slot."""
    return PersonaVerdict(
        persona=persona,  # type: ignore[arg-type]
        recommendation=recommendation,  # type: ignore[arg-type]
        lean=0.4,
        confidence=0.8,
        rationale=f"Escalation test rationale for {persona}.",
    )


def _valid_verdicts() -> tuple[PersonaVerdict, PersonaVerdict, PersonaVerdict]:
    """Return one convergent verdict per canonical persona."""
    return (_verdict("cro"), _verdict("growth"), _verdict("capital"))


def _inputs(**overrides: object) -> EscalationInputs:
    """Build escalation inputs with a success baseline, then apply overrides."""
    defaults: dict[str, object] = {
        "verdicts": _valid_verdicts(),
        "failures": (),
        "divergence": 0.10,
        "divergence_threshold": 0.50,
        "tier1_confidence": 0.90,
        "tier1_confidence_threshold": 0.30,
    }
    defaults.update(overrides)
    return EscalationInputs(**defaults)  # type: ignore[arg-type]


def _load_fixture(filename: str) -> EvidenceBundle:
    """Load a recorded v2 fixture without its metadata keys."""
    data = json.loads((FIXTURE_DIR / filename).read_text(encoding="utf-8"))
    data.pop("_fixture", None)
    data.pop("_version", None)
    return EvidenceBundle(**data)  # type: ignore[arg-type]


def test_success_row() -> None:
    """Table row 1: converged, confident, no failure -> success, no review."""
    result = evaluate_escalation(_inputs())
    assert result.status == "success"
    assert result.reasons == ()
    assert result.human_review_required is False


def test_divergence_row_escalates_at_the_boundary() -> None:
    """Table row 2: `divergence >= threshold` escalates (boundary included)."""
    result = evaluate_escalation(_inputs(divergence=0.50))
    assert result.status == "escalate"
    assert result.reasons == (EscalationReason.DIVERGENCE_THRESHOLD,)
    assert result.human_review_required is True


def test_divergence_below_threshold_does_not_escalate() -> None:
    """The `>=` boundary is the only divergence escalation point."""
    result = evaluate_escalation(_inputs(divergence=0.4999999))
    assert result.status == "success"


def test_low_tier1_confidence_row_escalates() -> None:
    """Table row 3: Tier 1 confidence `< threshold` escalates."""
    result = evaluate_escalation(_inputs(tier1_confidence=0.2999999))
    assert result.status == "escalate"
    assert result.reasons == (EscalationReason.TIER1_CONFIDENCE_BELOW_THRESHOLD,)
    assert result.human_review_required is True


def test_tier1_confidence_at_threshold_does_not_escalate() -> None:
    """Only strictly-below-confidence escalates; equality is accepted."""
    result = evaluate_escalation(_inputs(tier1_confidence=0.30))
    assert result.status == "success"


def test_fallback_provider_row_escalates() -> None:
    """Table row 4: any fallback-served persona escalates (fail-safe)."""
    result = evaluate_escalation(_inputs(fallback_used=True))
    assert result.status == "escalate"
    assert result.reasons == (EscalationReason.FALLBACK_PROVIDER,)
    assert result.human_review_required is True


def test_cost_unknown_row_escalates() -> None:
    """Table row 8 / Q-2: unknown cost escalates, never treated as $0."""
    result = evaluate_escalation(_inputs(cost_unknown=True))
    assert result.status == "escalate"
    assert result.reasons == (EscalationReason.COST_UNKNOWN,)
    assert result.human_review_required is True


@pytest.mark.parametrize(
    ("failure_reason", "expected_reason"),
    [
        (
            PersonaFailureReason.INVALID_AFTER_REPAIR,
            EscalationReason.PERSONA_INVALID_AFTER_REPAIR,
        ),
        (PersonaFailureReason.GATEWAY_FAILURE, EscalationReason.GATEWAY_FAILURE),
        (PersonaFailureReason.GATEWAY_TIMEOUT, EscalationReason.GATEWAY_TIMEOUT),
    ],
)
def test_persona_failure_rows_are_incomplete(
    failure_reason: PersonaFailureReason,
    expected_reason: EscalationReason,
) -> None:
    """Table rows 5-6: invalid-after-repair and gateway failure/timeout -> no report."""
    cro, growth, _capital = _valid_verdicts()
    result = evaluate_escalation(
        _inputs(
            verdicts=(cro, growth),
            failures=(PersonaFailure(persona="capital", reason=failure_reason),),
        )
    )
    assert result.status == "incomplete"
    assert result.reasons == (expected_reason,)
    assert result.human_review_required is True


def test_bound_breach_row_is_incomplete() -> None:
    """Table row 7: any call/token/time/cost bound breach -> incomplete."""
    result = evaluate_escalation(_inputs(bound_breached=True))
    assert result.status == "incomplete"
    assert result.reasons == (EscalationReason.BOUND_EXCEEDED,)
    assert result.human_review_required is True


def test_incomplete_precedence_suppresses_escalation_reasons() -> None:
    """Fixed precedence: incomplete wins even when every escalate condition holds."""
    cro, growth, _capital = _valid_verdicts()
    result = evaluate_escalation(
        _inputs(
            verdicts=(cro, growth),
            failures=(
                PersonaFailure(
                    persona="capital",
                    reason=PersonaFailureReason.GATEWAY_FAILURE,
                ),
            ),
            divergence=0.99,
            tier1_confidence=0.0,
            fallback_used=True,
            cost_unknown=True,
            bound_breached=True,
        )
    )
    assert result.status == "incomplete"
    assert result.reasons == (
        EscalationReason.GATEWAY_FAILURE,
        EscalationReason.BOUND_EXCEEDED,
    )
    assert EscalationReason.DIVERGENCE_THRESHOLD not in result.reasons
    assert EscalationReason.TIER1_CONFIDENCE_BELOW_THRESHOLD not in result.reasons
    assert EscalationReason.FALLBACK_PROVIDER not in result.reasons
    assert EscalationReason.COST_UNKNOWN not in result.reasons


def test_all_escalation_reasons_are_ordered_deterministically() -> None:
    """Reason codes are stable and emitted in fixed priority order."""
    result = evaluate_escalation(
        _inputs(
            divergence=0.90,
            tier1_confidence=0.10,
            fallback_used=True,
            cost_unknown=True,
        )
    )
    assert result.status == "escalate"
    assert result.reasons == (
        EscalationReason.DIVERGENCE_THRESHOLD,
        EscalationReason.TIER1_CONFIDENCE_BELOW_THRESHOLD,
        EscalationReason.FALLBACK_PROVIDER,
        EscalationReason.COST_UNKNOWN,
    )


def test_all_incomplete_reasons_are_ordered_deterministically() -> None:
    """Incomplete reasons follow persona-invalid, gateway, timeout, bound order."""
    cro, _growth, _capital = _valid_verdicts()
    result = evaluate_escalation(
        _inputs(
            verdicts=(cro,),
            failures=(
                PersonaFailure(
                    persona="growth",
                    reason=PersonaFailureReason.GATEWAY_TIMEOUT,
                ),
                PersonaFailure(
                    persona="capital",
                    reason=PersonaFailureReason.INVALID_AFTER_REPAIR,
                ),
            ),
            bound_breached=True,
        )
    )
    assert result.status == "incomplete"
    assert result.reasons == (
        EscalationReason.PERSONA_INVALID_AFTER_REPAIR,
        EscalationReason.GATEWAY_TIMEOUT,
        EscalationReason.BOUND_EXCEEDED,
    )


@pytest.mark.parametrize(
    "overrides",
    [
        # Two valid verdicts and no failure marker: one persona slot is missing.
        {"verdicts": _valid_verdicts()[:2]},
        # Three verdicts plus a failure: four slots for three personas.
        {
            "failures": (
                PersonaFailure(
                    persona="capital",
                    reason=PersonaFailureReason.GATEWAY_FAILURE,
                ),
            )
        },
        # A duplicated persona leaves another unrepresented.
        {
            "verdicts": (_verdict("cro"), _verdict("cro")),
            "failures": (
                PersonaFailure(
                    persona="capital",
                    reason=PersonaFailureReason.GATEWAY_FAILURE,
                ),
            ),
        },
    ],
)
def test_each_persona_must_appear_exactly_once(overrides: dict[str, object]) -> None:
    """A missing or duplicated persona slot cannot be mistaken for convergence."""
    with pytest.raises(ValueError):
        _inputs(**overrides)


@pytest.mark.parametrize(
    "confidence",
    [-0.01, 1.01],
)
def test_inputs_reject_out_of_range_values(confidence: float) -> None:
    """Convergence inputs are bounded at the contract boundary."""
    with pytest.raises(ValidationError):
        _inputs(tier1_confidence=confidence)


def test_no_outcome_implies_approval() -> None:
    """INV-10: the outcome model has no approval field and no approval status."""
    assert set(get_args(Tier3Status)) == {"success", "escalate", "incomplete"}
    assert not any("approv" in field for field in EscalationResult.model_fields)

    success = evaluate_escalation(_inputs())
    assert success.status == "success"
    assert not success.human_review_required
    # Success means the report may be assembled for a human; it is not approval.


def test_result_consistency_guard() -> None:
    """An internally inconsistent outcome cannot be constructed."""
    with pytest.raises(ValidationError):
        EscalationResult(
            status="success",
            reasons=(EscalationReason.DIVERGENCE_THRESHOLD,),
            human_review_required=False,
        )
    with pytest.raises(ValidationError):
        EscalationResult(status="escalate", reasons=(), human_review_required=True)
    with pytest.raises(ValidationError):
        EscalationResult(
            status="incomplete",
            reasons=(EscalationReason.BOUND_EXCEEDED,),
            human_review_required=False,
        )


def test_seed_cases_end_to_end_escalation() -> None:
    """SC-01 success; SC-02/03 diverge; SC-05 low confidence; SC-04 note below."""
    params = load_params("params.yaml")
    expected = {
        "sc_01_bundle.json": ("success", ()),
        "sc_02_bundle.json": (
            "escalate",
            (
                EscalationReason.DIVERGENCE_THRESHOLD,
                EscalationReason.TIER1_CONFIDENCE_BELOW_THRESHOLD,
            ),
        ),
        "sc_03_bundle.json": ("escalate", (EscalationReason.DIVERGENCE_THRESHOLD,)),
        "sc_05_bundle.json": (
            "escalate",
            (EscalationReason.TIER1_CONFIDENCE_BELOW_THRESHOLD,),
        ),
        # SC-04's verdicts are all `conditional` (rec distance 0), its divergence
        # is below threshold, and proxy B equals the provisional threshold
        # exactly. The approved table has no "limitations" row, so this path is
        # `success`; the fixture label describes persona-level evidence gaps, not
        # a convergence failure. Recorded as a Stage 2 observation for Stage 4.
        "sc_04_bundle.json": ("success", ()),
    }

    for filename, (status, reasons) in expected.items():
        bundle = _load_fixture(filename)
        assert bundle.persona_verdicts is not None
        verdicts = tuple(bundle.persona_verdicts.values())
        divergence = compute_divergence(verdicts)
        confidence = compute_tier1_confidence(
            bundle,
            params.tier3.tier1_confidence_proxy,
            band_dispersion_ref=params.tier3.band_dispersion_ref,
            thresholds=params.rating_thresholds,
        )
        result = evaluate_escalation(
            EscalationInputs(
                verdicts=verdicts,
                divergence=divergence,
                divergence_threshold=params.tier3.divergence_threshold,
                tier1_confidence=confidence,
                tier1_confidence_threshold=params.tier3.tier1_confidence_threshold,
            )
        )
        assert result.status == status, filename
        assert result.reasons == reasons, filename
