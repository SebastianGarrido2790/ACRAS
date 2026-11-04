"""Property and table tests for deterministic divergence (P4-03 / T3-FR-10/11).

Covers `spec.md` §6 acceptance criterion 3 and `plan.md` §3.1: range,
permutation invariance, symmetry, monotonicity in lean spread, the
recommendation-distance table, threshold boundary semantics, and the
zero-total-weight fail-safe.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from src.agents.orchestration.divergence import (
    ZERO_WEIGHT_DIVERGENCE,
    compute_divergence,
    divergence_reaches_threshold,
    lean_distance,
    pair_distance,
    pair_weight,
    recommendation_distance,
)
from src.schemas.evidence_bundle import EvidenceBundle, PersonaVerdict

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"

RECOMMENDATIONS = ("approve", "conditional", "reject")


def _verdict(
    persona: str,
    recommendation: str,
    lean: float,
    confidence: float,
) -> PersonaVerdict:
    """Build a valid verdict; the rationale just satisfies the schema minimum."""
    return PersonaVerdict(
        persona=persona,  # type: ignore[arg-type]
        recommendation=recommendation,  # type: ignore[arg-type]
        lean=lean,
        confidence=confidence,
        rationale=f"Divergence test rationale for {persona}.",
    )


def _trio(
    leans: Sequence[float] = (0.6, 0.0, -0.6),
    confidences: Sequence[float] = (0.8, 0.7, 0.6),
    recommendations: Sequence[str] = ("approve", "conditional", "reject"),
) -> tuple[PersonaVerdict, PersonaVerdict, PersonaVerdict]:
    """Build one verdict per canonical persona; sequences must have length 3."""
    return tuple(  # type: ignore[return-value]
        _verdict(persona, rec, lean, confidence)
        for persona, rec, lean, confidence in zip(
            ("cro", "growth", "capital"), recommendations, leans, confidences, strict=True
        )
    )


def _load_fixture(filename: str) -> EvidenceBundle:
    """Load a recorded v2 fixture without its metadata keys."""
    data = json.loads((FIXTURE_DIR / filename).read_text(encoding="utf-8"))
    data.pop("_fixture", None)
    data.pop("_version", None)
    return EvidenceBundle(**data)  # type: ignore[arg-type]


def test_recommendation_distance_table() -> None:
    """T3-FR-10: exact categorical distance for all nine ordered pairs."""
    expected = {
        ("approve", "approve"): 0.0,
        ("conditional", "conditional"): 0.0,
        ("reject", "reject"): 0.0,
        ("approve", "conditional"): 0.5,
        ("conditional", "approve"): 0.5,
        ("conditional", "reject"): 0.5,
        ("reject", "conditional"): 0.5,
        ("approve", "reject"): 1.0,
        ("reject", "approve"): 1.0,
    }
    for (rec_a, rec_b), distance in expected.items():
        assert recommendation_distance(rec_a, rec_b) == distance
    assert set(expected) == set(itertools.product(RECOMMENDATIONS, RECOMMENDATIONS))


def test_pair_distance_and_weight_formula() -> None:
    """T3-FR-10: pair distance is 0.5 rec + 0.5 lean; weight is the mean confidence."""
    approve = _verdict("cro", "approve", 0.6, 0.8)
    reject = _verdict("growth", "reject", -0.4, 0.6)

    assert lean_distance(approve, reject) == pytest.approx(0.5)
    assert pair_distance(approve, reject) == pytest.approx(0.75)
    assert pair_weight(approve, reject) == pytest.approx(0.7)


def test_divergence_matches_hand_computed_weighted_mean() -> None:
    """T3-FR-10: the confidence-weighted mean is computed over the three pairs."""
    verdicts = _trio(
        leans=(1.0, 0.0, -1.0),
        confidences=(0.8, 0.6, 0.4),
        recommendations=("approve", "conditional", "reject"),
    )
    # pair distances: 0.5, 1.0, 0.5; weights: 0.7, 0.6, 0.5
    # (0.7*0.5 + 0.6*1.0 + 0.5*0.5) / 1.8 = 1.2 / 1.8
    assert compute_divergence(verdicts) == pytest.approx(2.0 / 3.0)


def test_divergence_is_bounded() -> None:
    """T3-FR-10: every valid input combination stays in [0, 1]."""
    confidence_patterns = ((0.0, 0.0, 0.0), (0.0, 0.5, 1.0), (1.0, 1.0, 1.0))
    for recs in itertools.product(RECOMMENDATIONS, repeat=3):
        for leans in itertools.product((-1.0, 0.0, 1.0), repeat=3):
            for confidences in confidence_patterns:
                divergence = compute_divergence(_trio(leans, confidences, recs))
                assert 0.0 <= divergence <= 1.0


def test_divergence_is_permutation_invariant() -> None:
    """T3-FR-10: input order cannot change the result."""
    verdicts = _trio(
        leans=(0.9, -0.2, 0.4),
        confidences=(0.85, 0.55, 0.7),
        recommendations=("approve", "conditional", "reject"),
    )
    results = {
        compute_divergence(permutation)
        for permutation in itertools.permutations(verdicts)
    }
    assert len(results) == 1
    assert next(iter(results)) == pytest.approx(compute_divergence(verdicts))


def test_divergence_is_symmetric_in_each_pair() -> None:
    """T3-FR-10: no pair ordering or persona label can bias the distance."""
    a = _verdict("cro", "approve", 0.75, 0.9)
    b = _verdict("growth", "reject", -0.5, 0.4)
    assert recommendation_distance(a.recommendation, b.recommendation) == (
        recommendation_distance(b.recommendation, a.recommendation)
    )
    assert lean_distance(a, b) == lean_distance(b, a)
    assert pair_distance(a, b) == pair_distance(b, a)
    assert pair_weight(a, b) == pair_weight(b, a)

    mirrored = (
        _verdict("cro", "reject", -0.75, 0.9),
        _verdict("growth", "approve", 0.5, 0.4),
        _verdict("capital", "conditional", 0.0, 0.5),
    )
    original = (
        _verdict("cro", "approve", 0.75, 0.9),
        _verdict("growth", "reject", -0.5, 0.4),
        _verdict("capital", "conditional", 0.0, 0.5),
    )
    assert compute_divergence(mirrored) == pytest.approx(compute_divergence(original))


def test_divergence_is_monotone_in_lean_spread() -> None:
    """T3-FR-10: widening the lean spread never reduces divergence."""
    values = [
        compute_divergence(
            _trio(
                leans=(-spread, 0.0, spread),
                confidences=(0.8, 0.7, 0.6),
                recommendations=("approve", "approve", "approve"),
            )
        )
        for spread in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]
    assert values == sorted(values)
    assert values[0] == 0.0
    assert values[-1] > values[0]


def test_zero_total_weight_fails_safe_to_one() -> None:
    """T3-FR-10: zero weight is an escalation signal, not agreement."""
    verdicts = _trio(
        leans=(0.5, 0.5, 0.5),
        confidences=(0.0, 0.0, 0.0),
        recommendations=("approve", "approve", "approve"),
    )
    assert compute_divergence(verdicts) == ZERO_WEIGHT_DIVERGENCE == 1.0


def test_zero_weight_fails_safe_even_with_large_disagreement() -> None:
    """T3-FR-10: the fail-safe value does not depend on the verdict content."""
    verdicts = _trio(
        leans=(1.0, 0.0, -1.0),
        confidences=(0.0, 0.0, 0.0),
        recommendations=("approve", "conditional", "reject"),
    )
    assert compute_divergence(verdicts) == 1.0


@pytest.mark.parametrize(
    ("divergence", "threshold", "expected"),
    [
        (0.50, 0.50, True),
        (0.5000001, 0.50, True),
        (0.4999999, 0.50, False),
        (0.0, 0.0, True),
        (0.0, 1.0, False),
        (1.0, 1.0, True),
    ],
)
def test_threshold_boundary_uses_greater_or_equal(
    divergence: float, threshold: float, expected: bool
) -> None:
    """`spec.md` §4: the boundary belongs to escalation."""
    assert divergence_reaches_threshold(divergence, threshold) is expected


@pytest.mark.parametrize(
    ("divergence", "threshold"),
    [(-0.1, 0.5), (0.5, -0.1), (1.1, 0.5), (0.5, 1.1), (float("nan"), 0.5)],
)
def test_threshold_helper_rejects_out_of_range_values(
    divergence: float, threshold: float
) -> None:
    """Invalid threshold inputs fail loudly instead of silently disabling a guard."""
    with pytest.raises(ValueError):
        divergence_reaches_threshold(divergence, threshold)


@pytest.mark.parametrize("count", [0, 1, 2, 4])
def test_requires_exactly_three_verdicts(count: int) -> None:
    """T3-FR-10: the approved formula is defined over three canonical verdicts."""
    verdicts = list(
        _trio()[:1] * count  # duplicate input length is enough to test the guard
    )
    with pytest.raises(ValueError, match="exactly 3"):
        compute_divergence(verdicts)


def test_rejects_duplicate_or_non_canonical_personas() -> None:
    """A fan-in that repeats or substitutes a persona is not the approved input."""
    duplicated = (
        _verdict("cro", "approve", 0.5, 0.8),
        _verdict("cro", "approve", 0.4, 0.7),
        _verdict("capital", "approve", 0.3, 0.6),
    )
    with pytest.raises(ValueError, match="canonical personas"):
        compute_divergence(duplicated)


def test_seed_case_divergence_values() -> None:
    """Pins the recorded Stage 2 seed-case values (`stages_evidence.md`)."""
    expected = {
        "sc_01_bundle.json": 0.03335106382978724,
        "sc_02_bundle.json": 0.5861968085106383,
        "sc_03_bundle.json": 0.5401988636363636,
        "sc_04_bundle.json": 0.09791666666666667,
        "sc_05_bundle.json": 0.016597222222222222,
    }
    for filename, value in expected.items():
        bundle = _load_fixture(filename)
        assert bundle.persona_verdicts is not None
        verdicts = tuple(bundle.persona_verdicts.values())
        assert compute_divergence(verdicts) == pytest.approx(value)
