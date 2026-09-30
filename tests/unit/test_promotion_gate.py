"""Unit tests for Stage 4 Standalone Promotion & Calibration Gate Functions.

Governed by:
    INV-3 (ADR-003): Promotion requires calibration gate (Brier score) first,
        discrimination (AUC/KS) second. Strong AUC alone is never sufficient.
    PRD FR12: Block model promotion to serving unless candidate passes both.
    D-1.7: Standalone, unit-testable pure functions with zero dependency on the
        model training pipeline or MLflow.

Stage 4 Bidirectional Falsification:
    - Pass direction: Deliberately well-calibrated & discriminating -> PASSES.
    - Block direction 1: High-AUC (>0.95) but severely miscalibrated -> BLOCKED.
    - Block direction 2: Nominal base-rate predictions with chance AUC (0.50) -> BLOCKED.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.pipelines.training.promotion_gate import (
    CalibrationCheckResult,
    DiscriminationCheckResult,
    PromotionGateResult,
    check_calibration,
    check_discrimination,
    evaluate_promotion_gate,
)


def test_pure_function_independence() -> None:
    """Verify promotion_gate module imports cleanly with no MLflow or training dependency."""
    import sys

    assert "src.pipelines.training.promotion_gate" in sys.modules
    from src.pipelines.training.promotion_gate import evaluate_promotion_gate

    assert callable(evaluate_promotion_gate)


def test_falsification_pass_direction_well_calibrated_and_discriminating() -> None:
    """Falsification (Pass Direction): Perfectly calibrated and discriminating case MUST pass.

    Construct synthetic test data where predicted probabilities match empirical base rates:
    - 50 negatives with p = 0.01
    - 50 positives with p = 0.99
    Brier score ~ 0.0001 <= 0.030, AUC = 1.0 >= 0.85.
    """
    y_true = np.array([0] * 50 + [1] * 50)
    y_prob = np.array([0.01] * 50 + [0.99] * 50)

    cal_res = check_calibration(y_true, y_prob, brier_threshold=0.030)
    disc_res = check_discrimination(y_true, y_prob, auc_threshold=0.850)
    gate_res = evaluate_promotion_gate(
        y_true, y_prob, brier_threshold=0.030, auc_threshold=0.850
    )

    assert isinstance(cal_res, CalibrationCheckResult)
    assert isinstance(disc_res, DiscriminationCheckResult)
    assert isinstance(gate_res, PromotionGateResult)

    assert cal_res.passed is True
    assert cal_res.brier_score < 0.001
    assert disc_res.passed is True
    assert disc_res.roc_auc == 1.0

    # Overall promotion gate MUST approve
    assert gate_res.passed is True


def test_falsification_block_direction_high_auc_but_miscalibrated() -> None:
    """Falsification (INV-3 / FR12 Core Block Direction): Strong AUC alone MUST be blocked!

    Construct synthetic case with perfect ranking / discrimination (AUC = 1.0),
    but massive calibration distortion (all predictions scaled into [0.80, 0.95],
    even though 95% of cases are negative class 0).
    - Negatives (95 cases): p = 0.80
    - Positives (5 cases):  p = 0.95
    ROC-AUC is 1.0 (perfect discrimination).
    However, predicting p=0.80 on negatives yields Brier score:
    0.95*(0.80)^2 + 0.05*(0.05)^2 = 0.608 >> 0.030!
    """
    y_true = np.array([0] * 95 + [1] * 5)
    y_prob = np.array([0.80] * 95 + [0.95] * 5)

    cal_res = check_calibration(y_true, y_prob, brier_threshold=0.030)
    disc_res = check_discrimination(y_true, y_prob, auc_threshold=0.850)
    gate_res = evaluate_promotion_gate(
        y_true, y_prob, brier_threshold=0.030, auc_threshold=0.850
    )

    # Discrimination passes trivially
    assert disc_res.passed is True
    assert disc_res.roc_auc == 1.0

    # Calibration MUST fail loudly
    assert cal_res.passed is False
    assert cal_res.brier_score > 0.50

    # Gate MUST BLOCK promotion despite AUC=1.0!
    assert gate_res.passed is False
    assert "PROMOTION BLOCKED" in gate_res.reason
    assert "INV-3 Violation" in gate_res.reason


def test_falsification_block_direction_calibrated_base_rate_but_chance_discrimination() -> None:
    """Falsification (Discrimination Block): Flat constant prediction matching base rate.

    - Population has 3% positive rate (97 zeros, 3 ones).
    - Predict uniform mean base rate 0.03 for all samples.
    - Calibration: Brier ~ 0.029 <= 0.035 (passes calibration).
    - Discrimination: AUC is 0.50 (chance).
    Gate MUST BLOCK due to failing discrimination.
    """
    y_true = np.array([0] * 97 + [1] * 3)
    y_prob = np.array([0.03] * 100)

    cal_res = check_calibration(y_true, y_prob, brier_threshold=0.035)
    assert cal_res.passed is True

    disc_res = check_discrimination(y_true, y_prob, auc_threshold=0.850)
    assert disc_res.passed is False
    assert disc_res.roc_auc == 0.50

    gate_res = evaluate_promotion_gate(
        y_true, y_prob, brier_threshold=0.035, auc_threshold=0.850
    )
    assert gate_res.passed is False
    assert "FAILED discrimination" in gate_res.reason


def test_validation_errors_on_invalid_inputs() -> None:
    """Verify robust input validation on malformed inputs."""
    with pytest.raises(ValueError, match="Length mismatch"):
        check_calibration([0, 1], [0.5])

    with pytest.raises(ValueError, match="Length mismatch"):
        check_discrimination([0, 1], [0.5])

    with pytest.raises(ValueError, match="empty arrays"):
        check_calibration([], [])

    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        check_calibration([0, 1], [-0.1, 0.5])

    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        check_calibration([0, 1], [0.2, 1.2])

    with pytest.raises(ValueError, match="both positive and negative classes"):
        check_discrimination([0, 0, 0], [0.1, 0.2, 0.3])

