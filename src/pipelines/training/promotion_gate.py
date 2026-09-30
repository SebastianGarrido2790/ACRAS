"""Standalone Promotion & Calibration Gate Functions.

Governed by:
    INV-3 (ADR-003): No model version may be promoted to serving unless it passes
        BOTH a discrimination check (AUC/KS) AND a calibration check (Brier score /
        reliability curve). Strong AUC alone is never sufficient grounds for promotion.
    PRD FR12: Block model promotion to serving unless the candidate passes both
        a calibration check and a discrimination check.
    D-1.7: Standalone, unit-testable pure functions with zero dependency on the
        model training pipeline or MLflow.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from sklearn.metrics import brier_score_loss, roc_auc_score


@dataclass(frozen=True)
class CalibrationCheckResult:
    """Result of calibration check against a maximum Brier score threshold."""

    passed: bool
    brier_score: float
    threshold: float
    reason: str


@dataclass(frozen=True)
class DiscriminationCheckResult:
    """Result of discrimination check against a minimum ROC-AUC threshold."""

    passed: bool
    roc_auc: float
    threshold: float
    reason: str


@dataclass(frozen=True)
class PromotionGateResult:
    """Overall promotion verdict combining calibration and discrimination checks."""

    passed: bool
    calibration: CalibrationCheckResult
    discrimination: DiscriminationCheckResult
    reason: str



def check_calibration(
    y_true: Sequence[int | float] | np.ndarray,
    y_prob: Sequence[float] | np.ndarray,
    brier_threshold: float = 0.030,
) -> CalibrationCheckResult:
    """Evaluate whether predicted probabilities pass the calibration gate (INV-3 / FR12).

    Calibration requires empirical Brier score <= brier_threshold.

    Args:
        y_true: Ground truth binary target labels (0 or 1).
        y_prob: Estimated probabilities of default in [0.0, 1.0].
        brier_threshold: Maximum acceptable Brier score (default: 0.030).

    Returns:
        CalibrationCheckResult with pass/fail verdict and score.
    """
    y_true_arr = np.asarray(y_true, dtype=np.float64)
    y_prob_arr = np.asarray(y_prob, dtype=np.float64)

    if len(y_true_arr) != len(y_prob_arr):
        raise ValueError(
            f"Length mismatch: y_true has {len(y_true_arr)} elements, y_prob has {len(y_prob_arr)}"
        )
    if len(y_true_arr) == 0:
        raise ValueError("Cannot evaluate calibration on empty arrays.")

    if np.any(y_prob_arr < 0.0) or np.any(y_prob_arr > 1.0):
        raise ValueError("Predicted probabilities y_prob must lie in [0.0, 1.0].")

    brier = float(brier_score_loss(y_true_arr, y_prob_arr))
    passed = brier <= brier_threshold

    if passed:
        reason = f"PASS: Brier score {brier:.6f} <= threshold {brier_threshold:.6f}."
    else:
        reason = (
            f"FAIL (INV-3 Gate Blocked): Brier score {brier:.6f} exceeds "
            f"maximum threshold {brier_threshold:.6f}."
        )

    return CalibrationCheckResult(
        passed=passed,
        brier_score=brier,
        threshold=brier_threshold,
        reason=reason,
    )


def check_discrimination(
    y_true: Sequence[int | float] | np.ndarray,
    y_prob: Sequence[float] | np.ndarray,
    auc_threshold: float = 0.850,
) -> DiscriminationCheckResult:
    """Evaluate whether predictions pass the discrimination gate (INV-3 / FR12).

    Discrimination requires ROC-AUC >= auc_threshold.

    Args:
        y_true: Ground truth binary target labels (0 or 1).
        y_prob: Estimated probabilities of default in [0.0, 1.0].
        auc_threshold: Minimum acceptable ROC-AUC (default: 0.850).

    Returns:
        DiscriminationCheckResult with pass/fail verdict and score.
    """
    y_true_arr = np.asarray(y_true, dtype=np.float64)
    y_prob_arr = np.asarray(y_prob, dtype=np.float64)

    if len(y_true_arr) != len(y_prob_arr):
        raise ValueError(
            f"Length mismatch: y_true has {len(y_true_arr)} elements, y_prob has {len(y_prob_arr)}"
        )
    if len(y_true_arr) == 0:
        raise ValueError("Cannot evaluate discrimination on empty arrays.")

    unique_labels = np.unique(y_true_arr)
    if len(unique_labels) < 2:
        raise ValueError("ROC-AUC requires both positive and negative classes in y_true.")

    auc = float(roc_auc_score(y_true_arr, y_prob_arr))
    passed = auc >= auc_threshold

    if passed:
        reason = f"PASS: ROC-AUC {auc:.6f} >= threshold {auc_threshold:.6f}."
    else:
        reason = (
            f"FAIL (Discrimination Gate Blocked): ROC-AUC {auc:.6f} is below "
            f"minimum threshold {auc_threshold:.6f}."
        )

    return DiscriminationCheckResult(
        passed=passed,
        roc_auc=auc,
        threshold=auc_threshold,
        reason=reason,
    )

    reason: str


def evaluate_promotion_gate(
    y_true: Sequence[int | float] | np.ndarray,
    y_prob: Sequence[float] | np.ndarray,
    brier_threshold: float = 0.030,
    auc_threshold: float = 0.850,
) -> PromotionGateResult:
    """Evaluate full dual promotion gate per Non-Negotiable Invariant INV-3.

    A candidate model is promoted to serving IF AND ONLY IF it satisfies
    BOTH the calibration check (brier_score <= brier_threshold) AND
    the discrimination check (roc_auc >= auc_threshold).

    Strong AUC alone is NEVER sufficient for promotion.

    Args:
        y_true: Ground truth binary target labels (0 or 1).
        y_prob: Estimated probabilities of default in [0.0, 1.0].
        brier_threshold: Maximum acceptable Brier score.
        auc_threshold: Minimum acceptable ROC-AUC.

    Returns:
        PromotionGateResult containing joint verdict and individual component results.
    """
    cal_res = check_calibration(y_true, y_prob, brier_threshold=brier_threshold)
    disc_res = check_discrimination(y_true, y_prob, auc_threshold=auc_threshold)

    passed = cal_res.passed and disc_res.passed

    if passed:
        reason = (
            f"PROMOTION APPROVED (INV-3 Satisfied): Both calibration "
            f"(Brier={cal_res.brier_score:.6f} <= {brier_threshold}) and discrimination "
            f"(AUC={disc_res.roc_auc:.6f} >= {auc_threshold}) passed."
        )
    elif not cal_res.passed and disc_res.passed:
        reason = (
            f"PROMOTION BLOCKED (INV-3 Violation): Strong discrimination "
            f"(AUC={disc_res.roc_auc:.6f} >= {auc_threshold}), but FAILED calibration "
            f"(Brier={cal_res.brier_score:.6f} > {brier_threshold}). Good AUC alone is never "
            f"sufficient for promotion."
        )
    elif cal_res.passed and not disc_res.passed:
        reason = (
            f"PROMOTION BLOCKED: Passed calibration (Brier={cal_res.brier_score:.6f} "
            f"<= {brier_threshold}), but FAILED discrimination (AUC={disc_res.roc_auc:.6f} "
            f"< {auc_threshold})."
        )
    else:
        reason = (
            f"PROMOTION BLOCKED: FAILED BOTH calibration (Brier={cal_res.brier_score:.6f} "
            f"> {brier_threshold}) and discrimination (AUC={disc_res.roc_auc:.6f} "
            f"< {auc_threshold})."
        )

    return PromotionGateResult(
        passed=passed,
        calibration=cal_res,
        discrimination=disc_res,
        reason=reason,
    )

