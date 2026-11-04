"""Deterministic Tier 3 escalation with fixed precedence (P4-03).

Governed by:
    INV-9: divergence or low-confidence cases route to human-in-the-loop review.
    INV-10: the system is decision support only. No status returned here, and
        no path through this module, approves a loan. `success` means the
        convergence checks passed and a report may be assembled for human
        review; it never means "approved".
    T3-FR-13: exactly one of `success`, `escalate`, `incomplete`, with stable
        machine-readable reason codes.
    T3-FR-14: `escalate` and `incomplete` always require human review.
    `spec.md` §4: failure and escalation table. Precedence is fixed:
        `incomplete` (persona failed or a bound was breached)
        > `escalate` (divergence, Tier 1 confidence, fallback, unknown cost)
        > `success`.

Threshold semantics: divergence escalates at `>= threshold`; Tier 1 confidence
escalates below `< threshold` (the boundary does not escalate).

The module is pure: no I/O, gateway, network, or model call.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.agents.orchestration.divergence import CANONICAL_PERSONAS
from src.schemas.evidence_bundle import PersonaVerdict

#: Canonical persona key (INV-8).
PersonaKey = Literal["cro", "growth", "capital"]

#: The only outcomes the convergence core may return.
Tier3Status = Literal["success", "escalate", "incomplete"]


class PersonaFailureReason(StrEnum):
    """Why a persona produced no valid verdict (T3-FR-06/07, §4)."""

    INVALID_AFTER_REPAIR = "invalid_after_repair"
    GATEWAY_FAILURE = "gateway_failure"
    GATEWAY_TIMEOUT = "gateway_timeout"


class EscalationReason(StrEnum):
    """Stable machine-readable escalation reason codes (`spec.md` §4)."""

    PERSONA_INVALID_AFTER_REPAIR = "persona_invalid_after_repair"
    GATEWAY_FAILURE = "gateway_failure"
    GATEWAY_TIMEOUT = "gateway_timeout"
    BOUND_EXCEEDED = "bound_exceeded"
    DIVERGENCE_THRESHOLD = "divergence_threshold"
    TIER1_CONFIDENCE_BELOW_THRESHOLD = "tier1_confidence_below_threshold"
    FALLBACK_PROVIDER = "fallback_provider"
    COST_UNKNOWN = "cost_unknown"


class PersonaFailure(BaseModel):
    """A persona slot that failed and therefore cannot supply a verdict."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    persona: PersonaKey
    reason: PersonaFailureReason


class EscalationInputs(BaseModel):
    """Validated inputs for one escalation decision.

    Every canonical persona appears exactly once, either as a valid verdict or
    as a failure marker, so an incomplete fan-in cannot be mistaken for
    agreement.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdicts: tuple[PersonaVerdict, ...] = ()
    failures: tuple[PersonaFailure, ...] = ()
    divergence: float = Field(ge=0.0, le=1.0)
    divergence_threshold: float = Field(ge=0.0, le=1.0)
    tier1_confidence: float = Field(ge=0.0, le=1.0)
    tier1_confidence_threshold: float = Field(ge=0.0, le=1.0)
    fallback_used: bool = False
    bound_breached: bool = False
    cost_unknown: bool = False

    @model_validator(mode="after")
    def require_one_slot_per_persona(self) -> EscalationInputs:
        """Require exactly the three canonical personas across both lists."""
        personas = [verdict.persona for verdict in self.verdicts] + [
            failure.persona for failure in self.failures
        ]
        if len(personas) != 3:
            raise ValueError(
                "Escalation requires exactly 3 persona slots "
                f"(verdicts + failures); got {len(personas)}."
            )
        if len(set(personas)) != 3 or set(personas) != CANONICAL_PERSONAS:
            raise ValueError(
                f"Escalation requires the canonical personas "
                f"{sorted(CANONICAL_PERSONAS)} once each; got {sorted(personas)}."
            )
        return self


class EscalationResult(BaseModel):
    """Typed escalation outcome. Deliberately carries no approval field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Tier3Status
    reasons: tuple[EscalationReason, ...]
    human_review_required: bool

    @model_validator(mode="after")
    def reasons_and_review_flag_match_status(self) -> EscalationResult:
        """Keep the outcome internally consistent (INV-9 / T3-FR-14)."""
        if self.status == "success":
            if self.reasons:
                raise ValueError("A success outcome must not carry reasons.")
            if self.human_review_required:
                raise ValueError("A success outcome must not require human review.")
        else:
            if not self.reasons:
                raise ValueError(f"An {self.status} outcome must carry at least one reason.")
            if not self.human_review_required:
                raise ValueError(f"An {self.status} outcome must require human review.")
        return self


_FAILURE_REASON_MAP: dict[PersonaFailureReason, EscalationReason] = {
    PersonaFailureReason.INVALID_AFTER_REPAIR: (
        EscalationReason.PERSONA_INVALID_AFTER_REPAIR
    ),
    PersonaFailureReason.GATEWAY_FAILURE: EscalationReason.GATEWAY_FAILURE,
    PersonaFailureReason.GATEWAY_TIMEOUT: EscalationReason.GATEWAY_TIMEOUT,
}

_INCOMPLETE_PRIORITY: tuple[EscalationReason, ...] = (
    EscalationReason.PERSONA_INVALID_AFTER_REPAIR,
    EscalationReason.GATEWAY_FAILURE,
    EscalationReason.GATEWAY_TIMEOUT,
    EscalationReason.BOUND_EXCEEDED,
)

_ESCALATE_PRIORITY: tuple[EscalationReason, ...] = (
    EscalationReason.DIVERGENCE_THRESHOLD,
    EscalationReason.TIER1_CONFIDENCE_BELOW_THRESHOLD,
    EscalationReason.FALLBACK_PROVIDER,
    EscalationReason.COST_UNKNOWN,
)


def evaluate_escalation(inputs: EscalationInputs) -> EscalationResult:
    """Return the escalation outcome for one Tier 3 report.

    Precedence is fixed: any persona failure, gateway failure/timeout, or bound
    breach yields `incomplete` and suppresses every escalation reason. Only with
    all three valid verdicts and no bound breach do divergence, confidence,
    fallback provenance, or unknown cost yield `escalate`.

    Args:
        inputs: Validated convergence results, failure markers, and flags.

    Returns:
        A consistent `EscalationResult`; `escalate` and `incomplete` always
        require human review, and no outcome implies approval.
    """
    incomplete_reasons = _incomplete_reasons(inputs)
    if incomplete_reasons:
        return EscalationResult(
            status="incomplete",
            reasons=incomplete_reasons,
            human_review_required=True,
        )

    escalate_reasons = _escalate_reasons(inputs)
    if escalate_reasons:
        return EscalationResult(
            status="escalate",
            reasons=escalate_reasons,
            human_review_required=True,
        )

    return EscalationResult(
        status="success",
        reasons=(),
        human_review_required=False,
    )


def _incomplete_reasons(inputs: EscalationInputs) -> tuple[EscalationReason, ...]:
    """Return ordered reasons that force `incomplete` (empty when none)."""
    present = {_FAILURE_REASON_MAP[failure.reason] for failure in inputs.failures}
    if inputs.bound_breached:
        present.add(EscalationReason.BOUND_EXCEEDED)
    return _ordered(present, _INCOMPLETE_PRIORITY)


def _escalate_reasons(inputs: EscalationInputs) -> tuple[EscalationReason, ...]:
    """Return ordered reasons that force `escalate` (empty when none)."""
    present: set[EscalationReason] = set()
    if inputs.divergence >= inputs.divergence_threshold:
        present.add(EscalationReason.DIVERGENCE_THRESHOLD)
    if inputs.tier1_confidence < inputs.tier1_confidence_threshold:
        present.add(EscalationReason.TIER1_CONFIDENCE_BELOW_THRESHOLD)
    if inputs.fallback_used:
        present.add(EscalationReason.FALLBACK_PROVIDER)
    if inputs.cost_unknown:
        present.add(EscalationReason.COST_UNKNOWN)
    return _ordered(present, _ESCALATE_PRIORITY)


def _ordered(
    present: set[EscalationReason],
    priority: tuple[EscalationReason, ...],
) -> tuple[EscalationReason, ...]:
    """Return present reasons in the module's fixed priority order."""
    return tuple(reason for reason in priority if reason in present)
