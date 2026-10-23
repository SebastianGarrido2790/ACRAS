"""Unit tests for promotion-gate calibration-sensitivity analysis (W-A5 / R-06)."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.special import expit
from sklearn.metrics import brier_score_loss, roc_auc_score

from src.pipelines.training.gate_sensitivity import (
    LOGIT_CLIP,
    expected_calibration_error,
    find_logit_scale_trip,
    find_logit_shift_trip,
    logit_scale,
    logit_shift,
    sweep_logit_shift,
)


def _synthetic_calibrated(n: int = 5000, center: float = -4.0, seed: int = 0):
    """Deterministic, well-calibrated synthetic probabilities with a low base rate."""
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    p = expit(0.6 * x + center)
    y = rng.binomial(1, p).astype(np.float64)
    return y, p


def test_logit_shift_delta_zero_is_identity() -> None:
    _, p = _synthetic_calibrated()
    assert np.allclose(logit_shift(p, 0.0), p, atol=1e-12)
    assert np.allclose(logit_scale(p, 1.0), p, atol=1e-12)


def test_logit_shift_clips_extremes_finite() -> None:
    p = np.array([0.0, 1.0, 0.5])
    for delta in (0.0, 5.0, 100.0):
        out = logit_shift(p, delta)
        assert np.all(np.isfinite(out))
        assert np.all((out >= 0.0) & (out <= 1.0))
    out = logit_shift(p, 0.0)
    assert out[0] <= expit(-LOGIT_CLIP) + 1e-9
    assert out[1] >= 1.0 - expit(-LOGIT_CLIP) - 1e-9


def test_falsification_auc_invariant_brier_monotone() -> None:
    """|Delta AUC| <= 1e-12 across increasing shift; Brier monotone above the gate."""
    y, p = _synthetic_calibrated()
    base_brier = float(brier_score_loss(y, p))
    base_auc = float(roc_auc_score(y, p))
    assert base_brier < 0.030  # synthetic is inside the gate

    sweep = sweep_logit_shift(y, p, np.linspace(0.0, 2.0, 101))
    assert np.max(np.abs(sweep["auc"] - base_auc)) <= 1e-12
    assert sweep["brier"][0] == pytest.approx(base_brier, abs=1e-12)

    # Brier monotonically degrades once it is above the gate (the region of interest).
    above = sweep["brier"] >= 0.030
    brier_above = sweep["brier"][above]
    assert brier_above.size > 1
    assert np.all(np.diff(brier_above) >= -1e-12)
    assert brier_above[-1] > base_brier


def test_find_logit_shift_trip() -> None:
    y, p = _synthetic_calibrated()
    trip = find_logit_shift_trip(y, p, brier_threshold=0.030)
    assert trip.parameter == "delta"
    assert trip.trip_value > 0.0
    assert trip.brier_at_trip == pytest.approx(0.030, abs=1e-4)
    assert trip.mean_pd_shift > 0.0
    assert abs(trip.auc_at_trip - trip.auc_baseline) <= 1e-12


def test_find_logit_scale_trip() -> None:
    y, p = _synthetic_calibrated()
    trip = find_logit_scale_trip(y, p, brier_threshold=0.030)
    assert trip.parameter == "gamma"
    assert trip.trip_value < 1.0
    assert trip.brier_at_trip == pytest.approx(0.030, abs=1e-4)
    assert abs(trip.auc_at_trip - trip.auc_baseline) <= 1e-12


def test_find_trip_raises_when_baseline_already_above_threshold() -> None:
    y, p = _synthetic_calibrated(center=-1.0)  # high base rate -> Brier above gate
    assert float(brier_score_loss(y, p)) > 0.030
    with pytest.raises(ValueError):
        find_logit_shift_trip(y, p, brier_threshold=0.030)


def test_expected_calibration_error_near_zero_when_calibrated() -> None:
    y, p = _synthetic_calibrated()
    assert expected_calibration_error(y, p) < 0.03
