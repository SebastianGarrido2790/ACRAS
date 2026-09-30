"""Unit tests for Stage 3 Model Training & Cross-Validated Calibration.

Governed by:
    INV-1 (ADR-001): Deterministic core.
    INV-3 (ADR-003): Promotion requires calibration gate (Brier score) first,
        discrimination (AUC/KS) second. Strong AUC alone is never sufficient.
    ADR-017 (D-1.1): Three candidate models (XGBoost, LightGBM, LogisticRegression baseline).
    ADR-018 (D-1.2): 5-fold cross-validated calibration (CalibratedClassifierCV).
    ADR-019 (D-1.3): Class weighting vs unweighted empirical comparison.
    ADR-020 (D-1.4): Empirical comparison of Platt scaling vs Isotonic regression.

Stage 3 Falsification:
    Train a throwaway configuration on randomly shuffled labels and confirm AUC
    lands near chance (~0.50) and Brier score is degraded.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config.loader import load_params
from src.pipelines.feature.split import load_processed_data
from src.pipelines.training.train import (
    ModelEvaluationResult,
    run_label_shuffle_falsification,
    train_and_evaluate_all_models,
    train_and_evaluate_config,
)


@pytest.fixture(scope="module")
def processed_data_dir() -> Path:
    """Fixture ensuring processed data partitions exist."""
    p = Path("data/processed")
    if not (p / "X_train.parquet").exists():
        pytest.skip("Preprocessed parquet partitions not found in data/processed")
    return p


def test_label_shuffle_falsification(processed_data_dir: Path) -> None:
    """Falsification: Prove label-shuffled model achieves chance-level discrimination.

    Confirms absence of target/feature leakage between preprocessing and training.
    """
    result = run_label_shuffle_falsification(
        processed_dir=processed_data_dir,
        seed=12345,
    )
    # Chance AUC is 0.50. Shuffled labels with small test positive count (44)
    # should comfortably land under 0.60, far below the clean baseline (~0.92-0.96)
    assert result.roc_auc < 0.60
    assert result.roc_auc > 0.40
    # Brier score on shuffled model should be degraded compared to clean model (~0.020-0.025)
    assert result.brier_score > 0.030


def test_single_configuration_evaluation(processed_data_dir: Path) -> None:
    """Verify evaluation of a single cross-validated calibrated model."""
    params = load_params()
    X_tr, X_te, y_tr, y_te = load_processed_data(processed_dir=processed_data_dir)
    pos_weight = float((len(y_tr) - y_tr.sum()) / y_tr.sum())

    res = train_and_evaluate_config(
        X_train=X_tr,
        y_train=y_tr,
        X_test=X_te,
        y_test=y_te,
        model_family="logistic_regression",
        weighted=False,
        calibration_method="sigmoid",
        params=params,
        pos_weight=pos_weight,
    )

    assert isinstance(res, ModelEvaluationResult)
    assert res.brier_score < 0.030
    assert res.roc_auc > 0.90
    assert res.ks_statistic > 0.70
    assert len(res.prob_true) > 0
    assert len(res.prob_pred) > 0


def test_all_12_configurations_ranking(processed_data_dir: Path, tmp_path: Path) -> None:
    """Gate 3: Verify all 12 candidate configurations are evaluated and sorted calibration-first."""
    summary = train_and_evaluate_all_models(
        processed_dir=processed_data_dir,
        tracking_uri=tmp_path / "mlruns",
        experiment_name="test-training-suite",
        log_to_mlflow=True,
    )

    # All 12 configurations evaluated (3 models x 2 weightings x 2 calibration methods)
    assert len(summary.results) == 12

    # Verify Brier-score-first ordering: results must be monotonically non-decreasing in Brier score
    brier_scores = [r.brier_score for r in summary.results]
    assert brier_scores == sorted(brier_scores)

    # Winner must have the lowest Brier score
    assert summary.winner == summary.results[0]
    assert summary.winner.brier_score < 0.025
    assert summary.winner.roc_auc > 0.95
