"""Promotion-gate calibration-sensitivity analysis (R-06 / W-A5).

Pure, standalone functions with zero training-pipeline or MLflow dependency
(D-1.7 style). They quantify how far the promoted model's probabilities can be
miscalibrated (monotone logit-shift or logit-scale) before the INV-3 Brier gate
first trips, while ROC-AUC remains rank-invariant.

Governed by:
    INV-3 (ADR-003): promotion requires BOTH discrimination and calibration.
    R-06 (remediation plan): Tier 1 gate-strength and selection-leakage audit.
    W-A5 falsification: |Delta AUC| <= 1e-12 under monotone distortion; logits
        clipped to +-38 before the sigmoid; delta=0 reproduces the baseline Brier.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import expit, logit
from sklearn.metrics import brier_score_loss, roc_auc_score

#: Logit clipping bound applied before the sigmoid to avoid saturation ties and
#: non-finite values at extreme probabilities (W-A5 falsification).
LOGIT_CLIP: float = 38.0

#: Machine epsilon used to keep probabilities inside the logit domain.
_EPS: float = 1e-12


def _clip_logit(p: np.ndarray) -> np.ndarray:
    """Map probabilities into a clipped logit domain, then back-clip to +-38."""
    p_safe = np.clip(np.asarray(p, dtype=np.float64), _EPS, 1.0 - _EPS)
    return np.clip(logit(p_safe), -LOGIT_CLIP, LOGIT_CLIP)


def logit_shift(p: np.ndarray, delta: float) -> np.ndarray:
    """Apply a monotone additive logit shift: p' = sigmoid(logit(p) + delta)."""
    arr = np.asarray(p, dtype=np.float64)
    if delta == 0.0:
        return arr.copy()
    return expit(_clip_logit(arr) + delta)


def logit_scale(p: np.ndarray, gamma: float) -> np.ndarray:
    """Apply a monotone logit scaling: p' = sigmoid(gamma * logit(p))."""
    arr = np.asarray(p, dtype=np.float64)
    if gamma == 1.0:
        return arr.copy()
    return expit(gamma * _clip_logit(arr))


def expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Expected Calibration Error (ECE) with equal-width bins over [0, 1]."""
    y = np.asarray(y_true, dtype=np.float64)
    p = np.asarray(y_prob, dtype=np.float64)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total = len(p)
    ece = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (p >= lo) & (p <= hi) if i == n_bins - 1 else (p >= lo) & (p < hi)
        n_bin = int(mask.sum())
        if n_bin == 0:
            continue
        ece += (n_bin / total) * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return float(ece)


@dataclass(frozen=True)
class TripPoint:
    """Result of a gate-sensitivity trip search."""

    parameter: str
    trip_value: float
    brier_at_trip: float
    mean_pd_shift: float
    ece_at_trip: float
    auc_at_trip: float
    auc_baseline: float


def _find_trip(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    brier_threshold: float,
    *,
    distort,
    lo: float,
    hi: float,
    parameter: str,
    tol: float = 1e-6,
) -> TripPoint:
    """Bisect the first distortion value at which Brier first exceeds the gate."""
    baseline_brier = float(brier_score_loss(y_true, y_prob))
    baseline_auc = float(roc_auc_score(y_true, y_prob))
    if baseline_brier >= brier_threshold:
        raise ValueError("Baseline Brier already at/above threshold; trip is at 0.")

    while float(brier_score_loss(y_true, distort(y_prob, hi))) <= brier_threshold:
        hi *= 2.0
        if hi > 1e6:
            raise ValueError("Distortion never trips the threshold in range.")

    for _ in range(100):
        mid = (lo + hi) / 2.0
        if float(brier_score_loss(y_true, distort(y_prob, mid))) > brier_threshold:
            hi = mid
        else:
            lo = mid
    trip = (lo + hi) / 2.0

    distorted = distort(y_prob, trip)
    return TripPoint(
        parameter=parameter,
        trip_value=float(trip),
        brier_at_trip=float(brier_score_loss(y_true, distorted)),
        mean_pd_shift=float(np.mean(distorted) - np.mean(y_prob)),
        ece_at_trip=expected_calibration_error(y_true, distorted),
        auc_at_trip=float(roc_auc_score(y_true, distorted)),
        auc_baseline=baseline_auc,
    )


def find_logit_shift_trip(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    brier_threshold: float,
    *,
    tol: float = 1e-6,
) -> TripPoint:
    """Find delta* > 0 where the additive logit shift first trips the Brier gate."""
    return _find_trip(
        y_true,
        y_prob,
        brier_threshold,
        distort=lambda p, d: logit_shift(p, d),
        lo=0.0,
        hi=1.0,
        parameter="delta",
        tol=tol,
    )


def find_logit_scale_trip(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    brier_threshold: float,
    *,
    tol: float = 1e-6,
) -> TripPoint:
    """Find gamma* < 1 (underconfidence) where logit scaling first trips the gate.

    For a low-base-rate calibrated model, shrinking probabilities toward the base
    rate (gamma -> 0) raises predictions for the negative majority and increases
    Brier. Overconfidence (gamma > 1) instead pushes the negative majority toward
    zero and typically does not trip the gate.
    """
    y = np.asarray(y_true, dtype=np.float64)
    p = np.asarray(y_prob, dtype=np.float64)
    baseline_brier = float(brier_score_loss(y, p))
    baseline_auc = float(roc_auc_score(y, p))
    if baseline_brier >= brier_threshold:
        raise ValueError("Baseline Brier already at/above threshold; trip is at gamma=1.")

    if float(brier_score_loss(y, logit_scale(p, 0.0))) <= brier_threshold:
        raise ValueError("Underconfident scaling never trips the threshold in range.")

    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        # Brier decreases as gamma increases; tripped (brier > threshold) means
        # gamma < gamma*, so move the lower bound up toward gamma*.
        if float(brier_score_loss(y, logit_scale(p, mid))) > brier_threshold:
            lo = mid
        else:
            hi = mid
    trip = (lo + hi) / 2.0

    distorted = logit_scale(p, trip)
    return TripPoint(
        parameter="gamma",
        trip_value=float(trip),
        brier_at_trip=float(brier_score_loss(y, distorted)),
        mean_pd_shift=float(np.mean(distorted) - np.mean(p)),
        ece_at_trip=expected_calibration_error(y, distorted),
        auc_at_trip=float(roc_auc_score(y, distorted)),
        auc_baseline=baseline_auc,
    )


def sweep_logit_shift(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    deltas: np.ndarray,
) -> dict[str, np.ndarray]:
    """Return Brier/AUC/mean-PD across an increasing logit-shift sweep."""
    briers: list[float] = []
    aucs: list[float] = []
    means: list[float] = []
    for d in deltas:
        p = logit_shift(y_prob, float(d))
        briers.append(float(brier_score_loss(y_true, p)))
        aucs.append(float(roc_auc_score(y_true, p)))
        means.append(float(np.mean(p)))
    return {
        "delta": np.asarray(deltas, dtype=np.float64),
        "brier": np.asarray(briers, dtype=np.float64),
        "auc": np.asarray(aucs, dtype=np.float64),
        "mean_pd": np.asarray(means, dtype=np.float64),
    }
