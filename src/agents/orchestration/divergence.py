"""Deterministic divergence over the three persona verdicts (P4-03).

Governed by:
    INV-4 (ADR-004): divergence is computed deterministically over the
        structured verdict fields (`recommendation`, `lean`, `confidence`).
        No LLM judge participates in this calculation.
    D4-02/D4-03: approved confidence-weighted mean of pairwise distances.
        Zero total pair weight fails safe to `1.0` (never agreement).
    `plan.md` §3.1: exact formula, three canonical verdicts (three pairs).
    T3-FR-10: bounded `[0, 1]`, permutation-invariant, zero-weight fail-safe.
    T3-FR-11: no LLM, gateway, network, or I/O dependency.

Threshold semantics belong to escalation: a divergence equal to the threshold
escalates (`>=`). Use `divergence_reaches_threshold` rather than re-implementing
the comparison at a call site.

The module is pure: inputs are validated `PersonaVerdict` objects and the output
is a plain `float`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import combinations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.schemas.evidence_bundle import PersonaVerdict

#: The three canonical persona keys (INV-8 / ADR-016 contract).
CANONICAL_PERSONAS: frozenset[str] = frozenset({"cro", "growth", "capital"})

#: Fail-safe divergence when every pair has zero confidence weight.
ZERO_WEIGHT_DIVERGENCE: float = 1.0


def recommendation_distance(rec_a: str, rec_b: str) -> float:
    """Return the categorical recommendation distance for one pair.

    Args:
        rec_a: First canonical recommendation (`approve` / `conditional` / `reject`).
        rec_b: Second canonical recommendation.

    Returns:
        `0.0` when equal, `0.5` when exactly one is `conditional`, and `1.0`
        for the `approve` / `reject` opposition.
    """
    if rec_a == rec_b:
        return 0.0
    if "conditional" in (rec_a, rec_b):
        return 0.5
    return 1.0


def lean_distance(verdict_a: PersonaVerdict, verdict_b: PersonaVerdict) -> float:
    """Return the normalized directional-lean distance for one pair.

    `lean` lives in `[-1, 1]`, so the absolute difference divided by `2` is in
    `[0, 1]`.

    Args:
        verdict_a: First verdict.
        verdict_b: Second verdict.

    Returns:
        Lean distance in `[0, 1]`.
    """
    return abs(verdict_a.lean - verdict_b.lean) / 2.0


def pair_distance(verdict_a: PersonaVerdict, verdict_b: PersonaVerdict) -> float:
    """Return the equally weighted recommendation-plus-lean distance for a pair.

    Args:
        verdict_a: First verdict.
        verdict_b: Second verdict.

    Returns:
        Pair distance in `[0, 1]`.
    """
    return 0.5 * recommendation_distance(
        verdict_a.recommendation, verdict_b.recommendation
    ) + 0.5 * lean_distance(verdict_a, verdict_b)


def pair_weight(verdict_a: PersonaVerdict, verdict_b: PersonaVerdict) -> float:
    """Return the confidence weight for a pair: the mean of both confidences.

    Args:
        verdict_a: First verdict.
        verdict_b: Second verdict.

    Returns:
        Pair weight in `[0, 1]`.
    """
    return (verdict_a.confidence + verdict_b.confidence) / 2.0


def compute_divergence(verdicts: Sequence[PersonaVerdict]) -> float:
    """Return the confidence-weighted mean of the three pairwise distances.

    Exactly three distinct canonical verdicts are required, producing three
    unordered pairs. The result is bounded `[0, 1]`, independent of input order,
    and returns `1.0` when the total pair weight is zero. That fail-safe is an
    escalation signal, not evidence of agreement.

    Args:
        verdicts: The three persona verdicts (`cro`, `growth`, `capital`),
            in any order.

    Returns:
        Divergence in `[0, 1]`.

    Raises:
        ValueError: If the input is not exactly the three canonical personas.
    """
    _require_three_canonical_verdicts(verdicts)

    pairs = list(combinations(verdicts, 2))
    total_weight = math.fsum(pair_weight(a, b) for a, b in pairs)
    if total_weight == 0.0:
        return ZERO_WEIGHT_DIVERGENCE

    weighted_distance = math.fsum(
        pair_weight(a, b) * pair_distance(a, b) for a, b in pairs
    )
    return _clamp_unit(weighted_distance / total_weight)


def divergence_reaches_threshold(divergence: float, threshold: float) -> bool:
    """Return whether a divergence escalates under the approved `>=` semantics.

    Args:
        divergence: Divergence in `[0, 1]`.
        threshold: Configured `tier3.divergence_threshold` in `[0, 1]`.

    Returns:
        `True` when `divergence >= threshold`; the boundary escalates.

    Raises:
        ValueError: If either value is non-finite or outside `[0, 1]`.
    """
    for name, value in (("divergence", divergence), ("threshold", threshold)):
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be a finite value in [0.0, 1.0]; got {value!r}.")
    return divergence >= threshold


def _require_three_canonical_verdicts(verdicts: Sequence[PersonaVerdict]) -> None:
    """Reject inputs that cannot produce the approved three-pair calculation."""
    if len(verdicts) != 3:
        raise ValueError(
            f"Divergence requires exactly 3 verdicts; got {len(verdicts)}."
        )
    personas = [verdict.persona for verdict in verdicts]
    if len(set(personas)) != 3 or set(personas) != CANONICAL_PERSONAS:
        raise ValueError(
            f"Divergence requires the canonical personas {sorted(CANONICAL_PERSONAS)}; "
            f"got {sorted(personas)}."
        )


def _clamp_unit(value: float) -> float:
    """Clamp a floating-point result to `[0, 1]` against arithmetic drift."""
    return min(1.0, max(0.0, value))
