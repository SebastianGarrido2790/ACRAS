"""Tests for both Tier 1 confidence proxies (P4-03 / T3-FR-12).

Covers `plan.md` §3.2 and the Stage 2 proxy comparison: analytic edge cases
(`p50 <= 0`, out-of-range `pd`, boundary, bucket center, open-ended buckets),
malformed configuration, and the recorded seed-case table used for selection.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.agents.orchestration.tier1_confidence import (
    PROXY_BAND_DISPERSION,
    PROXY_RATING_BOUNDARY_MARGIN,
    band_dispersion_confidence,
    compute_tier1_confidence,
    rating_boundary_margin_confidence,
)
from src.config.loader import RatingThreshold, load_params
from src.schemas.evidence_bundle import EvidenceBundle, PDBand

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"

SEED_CASES = (
    "sc_01_bundle.json",
    "sc_02_bundle.json",
    "sc_03_bundle.json",
    "sc_04_bundle.json",
    "sc_05_bundle.json",
)

#: Pre-registered Stage 2 values (see `stages_evidence.md` §Stage 2).
EXPECTED_PROXY_A = {
    "sc_01_bundle.json": 0.800,
    "sc_02_bundle.json": 0.4444444444444444,
    "sc_03_bundle.json": 0.400,
    "sc_04_bundle.json": 0.5769230769230769,
    "sc_05_bundle.json": 0.000,
}

EXPECTED_PROXY_B = {
    "sc_01_bundle.json": 1.000,
    "sc_02_bundle.json": 0.2857142857142857,
    "sc_03_bundle.json": 0.5714285714285714,
    "sc_04_bundle.json": 0.300,
    "sc_05_bundle.json": 0.100,
}


def _load_fixture(filename: str) -> EvidenceBundle:
    """Load a recorded v2 fixture without its metadata keys."""
    data = json.loads((FIXTURE_DIR / filename).read_text(encoding="utf-8"))
    data.pop("_fixture", None)
    data.pop("_version", None)
    return EvidenceBundle(**data)  # type: ignore[arg-type]


def _thresholds() -> list[RatingThreshold]:
    """Return the canonical rating brackets from params.yaml."""
    return load_params("params.yaml").rating_thresholds


@pytest.mark.parametrize(
    ("pd_band", "expected"),
    [
        (PDBand(p10=0.008, p50=0.010, p90=0.012), 0.800),
        (PDBand(p10=0.030, p50=0.045, p90=0.080), 0.4444444444444444),
        (PDBand(p10=0.015, p50=0.025, p90=0.045), 0.400),
        (PDBand(p10=0.010, p50=0.010, p90=0.010), 1.000),
        (PDBand(p10=0.000, p50=0.010, p90=0.100), 0.000),
    ],
)
def test_proxy_a_analytic_values(pd_band: PDBand, expected: float) -> None:
    """T3-FR-12: proxy A follows `1 - min(1, relative_width / ref)`."""
    assert band_dispersion_confidence(pd_band, reference_width=2.0) == pytest.approx(expected)


def test_proxy_a_zero_median_fails_safe() -> None:
    """`plan.md` §3.2: an undefined relative width is not high confidence."""
    band = PDBand(p10=0.0, p50=0.0, p90=0.010)
    assert band_dispersion_confidence(band, reference_width=2.0) == 0.0


@pytest.mark.parametrize("reference_width", [0.0, -1.0, float("nan"), float("inf")])
def test_proxy_a_rejects_invalid_normalizer(reference_width: float) -> None:
    """A bad normalizer must fail at the call site, not silently distort confidence."""
    band = PDBand(p10=0.008, p50=0.010, p90=0.012)
    with pytest.raises(ValueError):
        band_dispersion_confidence(band, reference_width=reference_width)


@pytest.mark.parametrize(
    ("pd", "expected"),
    [
        # BBB bucket [0.005, 0.015]: center = 1.0, boundary = 0.0.
        (0.0100, 1.000),
        (0.0150, 0.000),
        # SC-05 sits close to the BBB upper boundary.
        (0.0145, 0.100),
        # SC-02 / SC-03 / SC-04.
        (0.0450, 0.2857142857142857),
        (0.0250, 0.5714285714285714),
        (0.0650, 0.300),
        # AAA lowest bucket: single finite boundary 0.001, AA half-width 0.00075.
        (0.0000, 1.000),
        (0.0005, 0.6666666666666666),
        (0.0010, 0.000),
        # CCC/C highest bucket: single finite boundary 0.15, B half-width 0.05.
        (0.1500, 0.000),
        (0.1750, 0.500),
        (0.2000, 1.000),
        # PD domain ceiling stays high-confidence for the worst rating bucket.
        (1.0000, 1.000),
    ],
)
def test_proxy_b_analytic_values(pd: float, expected: float) -> None:
    """T3-FR-12: proxy B is 0.0 on a boundary and 1.0 at the bucket center."""
    assert rating_boundary_margin_confidence(pd, _thresholds()) == pytest.approx(expected)


def test_proxy_b_is_near_zero_immediately_above_a_boundary() -> None:
    """Decision instability does not reset abruptly when the bucket flips."""
    confidence = rating_boundary_margin_confidence(0.015001, _thresholds())
    assert 0.0 < confidence < 0.001


@pytest.mark.parametrize("pd", [-0.01, 1.01, float("nan"), float("inf")])
def test_proxy_b_out_of_range_fails_safe(pd: float) -> None:
    """`plan.md` §3.2: a PD outside the configured bounds returns 0.0."""
    assert rating_boundary_margin_confidence(pd, _thresholds()) == 0.0


def test_proxy_b_pd_above_every_bound_fails_safe() -> None:
    """A table whose final bound is below 1.0 leaves late PDs unrated (0.0)."""
    thresholds = [
        RatingThreshold(rating="A", max_pd=0.005),
        RatingThreshold(rating="B", max_pd=0.050),
    ]
    assert rating_boundary_margin_confidence(0.060, thresholds) == 0.0


def test_proxy_b_rejects_malformed_threshold_tables() -> None:
    """A malformed table fails loudly instead of mis-bucketing PD."""
    with pytest.raises(ValueError, match="At least two"):
        rating_boundary_margin_confidence(0.01, [RatingThreshold(rating="A", max_pd=0.005)])

    with pytest.raises(ValueError, match="strictly increasing"):
        rating_boundary_margin_confidence(
            0.01,
            [
                RatingThreshold(rating="AA", max_pd=0.010),
                RatingThreshold(rating="A", max_pd=0.005),
            ],
        )

    with pytest.raises(ValueError, match="first rating threshold"):
        rating_boundary_margin_confidence(
            0.01,
            [
                RatingThreshold(rating="AAA", max_pd=0.0),
                RatingThreshold(rating="B", max_pd=0.05),
            ],
        )


def test_proxy_b_honors_inclusive_bucket_mapping() -> None:
    """The rating map is inclusive (`pd <= max_pd`), so the boundary is unstable."""
    thresholds = _thresholds()
    assert rating_boundary_margin_confidence(0.015, thresholds) == 0.0
    assert rating_boundary_margin_confidence(0.005, thresholds) == 0.0


def test_dispatcher_selects_both_proxies() -> None:
    """T3-FR-12: both proxies stay callable through the configured selector."""
    bundle = _load_fixture("sc_01_bundle.json")
    params = load_params("params.yaml")

    proxy_a = compute_tier1_confidence(
        bundle,
        PROXY_BAND_DISPERSION,
        band_dispersion_ref=params.tier3.band_dispersion_ref,
        thresholds=params.rating_thresholds,
    )
    proxy_b = compute_tier1_confidence(
        bundle,
        PROXY_RATING_BOUNDARY_MARGIN,
        band_dispersion_ref=params.tier3.band_dispersion_ref,
        thresholds=params.rating_thresholds,
    )
    assert proxy_a == pytest.approx(0.800)
    assert proxy_b == pytest.approx(1.000)


def test_dispatcher_missing_inputs_fail_safe() -> None:
    """Absence of the proxy's required Tier 1/Tier 2 input is not high confidence."""
    bundle = _load_fixture("sc_01_bundle.json")
    params = load_params("params.yaml")

    without_band = bundle.model_copy(update={"pd_band": None})
    assert (
        compute_tier1_confidence(
            without_band,
            PROXY_BAND_DISPERSION,
            band_dispersion_ref=params.tier3.band_dispersion_ref,
            thresholds=params.rating_thresholds,
        )
        == 0.0
    )

    without_pd = bundle.model_copy(update={"pd": None})
    assert (
        compute_tier1_confidence(
            without_pd,
            PROXY_RATING_BOUNDARY_MARGIN,
            band_dispersion_ref=params.tier3.band_dispersion_ref,
            thresholds=params.rating_thresholds,
        )
        == 0.0
    )


def test_dispatcher_rejects_unknown_proxy() -> None:
    """An unknown proxy name must never fall through to a default."""
    bundle = _load_fixture("sc_01_bundle.json")
    params = load_params("params.yaml")
    with pytest.raises(ValueError, match="Unsupported"):
        compute_tier1_confidence(
            bundle,
            "llm_judge",  # type: ignore[arg-type]
            band_dispersion_ref=params.tier3.band_dispersion_ref,
            thresholds=params.rating_thresholds,
        )


def test_seed_case_proxy_table() -> None:
    """Pins the recorded proxy comparison table (`stages_evidence.md` §Stage 2)."""
    params = load_params("params.yaml")
    for filename in SEED_CASES:
        bundle = _load_fixture(filename)
        proxy_a = compute_tier1_confidence(
            bundle,
            PROXY_BAND_DISPERSION,
            band_dispersion_ref=params.tier3.band_dispersion_ref,
            thresholds=params.rating_thresholds,
        )
        proxy_b = compute_tier1_confidence(
            bundle,
            PROXY_RATING_BOUNDARY_MARGIN,
            band_dispersion_ref=params.tier3.band_dispersion_ref,
            thresholds=params.rating_thresholds,
        )
        assert proxy_a == pytest.approx(EXPECTED_PROXY_A[filename], abs=1e-9)
        assert proxy_b == pytest.approx(EXPECTED_PROXY_B[filename], abs=1e-9)


def test_approved_selection_criterion_and_configured_proxy() -> None:
    """T3-FR-12 / Q-1: low case below threshold, high case at or above it.

    Post-repair both proxies satisfy the literal separation check (SC-05 below,
    SC-01 above). The selection therefore rests on Q-1's construct-validity
    rationale: proxy B measures distance to the rating decision boundary
    (decision stability), while proxy A measures relative band width. Proxy B
    is the pre-registered selection; proxy A remains implemented.
    """
    params = load_params("params.yaml")
    threshold = params.tier3.tier1_confidence_threshold

    assert EXPECTED_PROXY_B["sc_05_bundle.json"] < threshold
    assert EXPECTED_PROXY_B["sc_01_bundle.json"] >= threshold
    assert EXPECTED_PROXY_A["sc_05_bundle.json"] < threshold
    assert EXPECTED_PROXY_A["sc_01_bundle.json"] >= threshold

    assert params.tier3.tier1_confidence_proxy == PROXY_RATING_BOUNDARY_MARGIN
    assert params.tier3.calibration == "provisional-phase5"
