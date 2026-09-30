"""Unit tests for Stage 5 Model Promotion, Freezing, and PD-to-Rating Mapping.

Governed by:
    INV-3 (ADR-003): Dual promotion gate: calibration first, discrimination second.
    ADR-021 (D-1.5): Fixed illustrative PD-to-credit-rating mapping table.
    ADR-022 (D-1.6): Model serialization: MLflow tracking, lean joblib bundle for serving.
    ADR-025 (D-1.11): Fitted YeoJohnsonTransformer bundled with model for parity.
    ADR-027: Winning XGBoost unweighted isotonic model promoted and verified.

Stage 5 Falsifications:
    1. Rating mapping unit tests: exact boundary cutoffs and threshold behavior.
    2. Promotion gate falsification: A deliberately miscalibrated stand-in model
       with high AUC MUST be rejected by the actual promote_and_export_model function.
    3. Export bundle round-trip test: Reloaded joblib bundle predictions on held-out test
       split match pre-export predictions with 100% numerical equality.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression

from src.config.loader import load_params
from src.pipelines.feature.split import load_processed_data
from src.pipelines.feature.transform import YeoJohnsonTransformer
from src.pipelines.training.promote import (
    PromotedModelBundle,
    PromotionGateError,
    load_promoted_bundle,
    promote_and_export_model,
    run_stage_5_promotion,
)
from src.pipelines.training.rating_mapping import map_pd_to_credit_rating
from src.pipelines.training.train import ModelEvaluationResult


@pytest.fixture(scope="module")
def processed_data_dir() -> Path:
    """Fixture ensuring preprocessed data partitions exist."""
    p = Path("data/processed")
    if not (p / "X_train.parquet").exists():
        pytest.skip("Preprocessed parquet partitions not found in data/processed")
    return p



# =============================================================================
# 1. PD-to-Rating Mapping Unit Tests (D-1.5 / ADR-021)
# =============================================================================


def test_rating_mapping_exact_boundaries() -> None:
    """Verify rating assignment at exact threshold boundaries from params.yaml.

    Thresholds:
      AAA   <= 0.001
      AA    <= 0.0025
      A     <= 0.005
      BBB   <= 0.015
      BB    <= 0.050
      B     <= 0.150
      CCC/C <= 1.000
    """
    params = load_params()
    thresholds = params.rating_thresholds

    assert map_pd_to_credit_rating(0.000, thresholds) == "AAA"
    assert map_pd_to_credit_rating(0.001, thresholds) == "AAA"
    assert map_pd_to_credit_rating(0.0025, thresholds) == "AA"
    assert map_pd_to_credit_rating(0.005, thresholds) == "A"
    assert map_pd_to_credit_rating(0.015, thresholds) == "BBB"
    assert map_pd_to_credit_rating(0.050, thresholds) == "BB"
    assert map_pd_to_credit_rating(0.150, thresholds) == "B"
    assert map_pd_to_credit_rating(1.000, thresholds) == "CCC/C"


def test_rating_mapping_delta_neighborhoods() -> None:
    """Verify rating shifts correctly just above and just below cutoffs."""
    params = load_params()
    t = params.rating_thresholds
    eps = 1e-6

    # Just above AAA cutoff -> AA
    assert map_pd_to_credit_rating(0.001 + eps, t) == "AA"
    assert map_pd_to_credit_rating(0.001 - eps, t) == "AAA"

    # Just above AA cutoff -> A
    assert map_pd_to_credit_rating(0.0025 + eps, t) == "A"
    assert map_pd_to_credit_rating(0.0025 - eps, t) == "AA"

    # Just above BB cutoff -> B
    assert map_pd_to_credit_rating(0.050 + eps, t) == "B"
    assert map_pd_to_credit_rating(0.050 - eps, t) == "BB"

    # Default loader when thresholds=None
    assert map_pd_to_credit_rating(0.080) == "B"


def test_rating_mapping_input_validation() -> None:
    """Verify out-of-range probabilities or empty thresholds raise ValueError."""
    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        map_pd_to_credit_rating(-0.01)

    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        map_pd_to_credit_rating(1.0001)

    with pytest.raises(ValueError, match="Threshold table is empty"):
        map_pd_to_credit_rating(0.05, thresholds=[])



# =============================================================================
# 2. Stage 5 Promotion Falsification & Gate Tests
# =============================================================================


def test_falsification_corrupted_standin_blocked_at_promotion_step(
    processed_data_dir: Path,
    tmp_path: Path,
) -> None:
    """Falsification: A miscalibrated model MUST be blocked by promote_and_export_model.

    We substitute a stand-in model that has high AUC (>0.90) but compressed high probabilities
    (p in [0.75, 0.99] on mostly negative class), yielding Brier ~ 0.50 >> 0.030.
    Must raise PromotionGateError and produce zero exported artifact.
    """
    params = load_params()
    X_tr, X_te, y_tr, y_te = load_processed_data(processed_dir=processed_data_dir)

    clf = CalibratedClassifierCV(
        estimator=LogisticRegression(max_iter=500, random_state=42),
        method="sigmoid",
        cv=2,
    )
    clf.fit(X_tr, y_tr)

    raw_probs = clf.predict_proba(X_te)[:, 1]
    corrupted_probs = 0.75 + 0.24 * raw_probs

    dummy_eval = ModelEvaluationResult(
        model_family="corrupted_standin",
        weighted=False,
        calibration_method="sigmoid",
        brier_score=0.56,
        roc_auc=0.92,
        ks_statistic=0.70,
        prob_true=[0.0],
        prob_pred=[0.8],
        model=clf,
    )

    transformer = YeoJohnsonTransformer()
    output_bundle = tmp_path / "should_not_exist.joblib"

    with pytest.raises(PromotionGateError, match="Model promotion rejected"):
        promote_and_export_model(
            model_eval=dummy_eval,
            transformer=transformer,
            y_test=y_te,
            test_probs=corrupted_probs,
            output_bundle_path=output_bundle,
            register_in_mlflow=False,
            params=params,
        )

    assert not output_bundle.exists()


def test_stage_5_winner_promotion_and_bundle_roundtrip(
    processed_data_dir: Path,
    tmp_path: Path,
) -> None:
    """Gate 5: Real Stage 3 winner passes promotion, exports bundle, and round-trips identically."""
    bundle_path = tmp_path / "promoted_model_bundle.joblib"

    bundle, gate_res = run_stage_5_promotion(
        processed_dir=processed_data_dir,
        transformer_path="artifacts/preprocessor.joblib",
        output_bundle_path=bundle_path,
        register_in_mlflow=True,
        tracking_uri=tmp_path / "mlruns",
        experiment_name="test-promotion-suite",
    )

    assert gate_res.passed is True
    assert bundle.brier_score <= 0.030
    assert bundle.roc_auc >= 0.850
    assert bundle.model_family == "xgboost"
    assert bundle.calibration_method == "isotonic"
    assert bundle.weighted is False

    assert bundle_path.is_file()

    loaded = load_promoted_bundle(bundle_path)
    assert isinstance(loaded, PromotedModelBundle)
    assert loaded.model_family == bundle.model_family
    assert loaded.calibration_method == bundle.calibration_method
    assert loaded.weighted == bundle.weighted
    assert loaded.brier_score == bundle.brier_score
    assert loaded.roc_auc == bundle.roc_auc

    _, X_te, _, _ = load_processed_data(processed_dir=processed_data_dir)
    orig_preds = bundle.model.predict_proba(X_te)[:, 1]
    loaded_preds = loaded.model.predict_proba(X_te)[:, 1]
    assert np.array_equal(orig_preds, loaded_preds)

