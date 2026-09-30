"""Model Promotion, Freezing, and Export Pipeline.

Governed by:
    INV-3 (ADR-003): Promotion requires passing calibration gate (Brier score) first,
        discrimination (ROC-AUC) second. Strong AUC alone is never sufficient.
    ADR-010: Separation of training and serving boundaries.
    ADR-022 (D-1.6): Model serialization & serving boundary: MLflow for tracking & registry,
        lean joblib bundle export for serving (zero MLflow dependency in serving container).
    ADR-025 (D-1.11): Fitted Yeo-Johnson transformer exported together with frozen model
        to guarantee training-serving parity.
    ADR-027: Record promoted winning model configuration and metrics.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import mlflow
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV

from src.config.loader import ProjectParams, load_params
from src.pipelines.feature.split import load_processed_data, load_transformer
from src.pipelines.feature.transform import YeoJohnsonTransformer
from src.pipelines.training.promotion_gate import (
    PromotionGateResult,
    evaluate_promotion_gate,
)
from src.pipelines.training.train import (
    DEFAULT_TRACKING_DIR,
    DEFAULT_TRAINING_EXPERIMENT,
    ModelEvaluationResult,
    train_and_evaluate_config,
)
from src.utils.exceptions import ACRASValidationError

DEFAULT_PROMOTED_MODEL_NAME: str = "acras-tier1-pd-model"
DEFAULT_EXPORT_PATH: str = "artifacts/promoted_model_bundle.joblib"


class PromotionGateError(ACRASValidationError):
    """Raised when a candidate model fails the INV-3 promotion gate."""


@dataclass(frozen=True)
class PromotedModelBundle:
    """Strongly-typed container for the exported Tier 1 model artifact."""

    model: CalibratedClassifierCV
    transformer: YeoJohnsonTransformer
    model_family: str
    weighted: bool
    calibration_method: str
    brier_score: float
    roc_auc: float
    ks_statistic: float


def build_promoted_bundle_dict(bundle: PromotedModelBundle) -> dict[str, Any]:
    """Convert bundle dataclass into serializable dictionary."""
    return {
        "model": bundle.model,
        "transformer": bundle.transformer,
        "model_family": bundle.model_family,
        "weighted": bundle.weighted,
        "calibration_method": bundle.calibration_method,
        "brier_score": bundle.brier_score,
        "roc_auc": bundle.roc_auc,
        "ks_statistic": bundle.ks_statistic,
    }


def load_promoted_bundle(
    bundle_path: str | Path = DEFAULT_EXPORT_PATH,
) -> PromotedModelBundle:
    """Load and validate the promoted model bundle artifact.

    Args:
        bundle_path: Path to the serialized joblib bundle.

    Returns:
        PromotedModelBundle instance.
    """
    path = Path(bundle_path)
    if not path.is_file():
        raise FileNotFoundError(f"Promoted model bundle not found at: {path.resolve()}")

    data: Any = joblib.load(path)
    if not isinstance(data, dict):
        raise TypeError(f"Expected dictionary bundle, got {type(data).__name__}")

    required_keys = {
        "model",
        "transformer",
        "model_family",
        "weighted",
        "calibration_method",
        "brier_score",
        "roc_auc",
        "ks_statistic",
    }
    missing = required_keys - set(data.keys())
    if missing:
        raise ValueError(f"Corrupted model bundle; missing keys: {missing}")

    return PromotedModelBundle(
        model=data["model"],
        transformer=data["transformer"],
        model_family=str(data["model_family"]),
        weighted=bool(data["weighted"]),
        calibration_method=str(data["calibration_method"]),
        brier_score=float(data["brier_score"]),
        roc_auc=float(data["roc_auc"]),
        ks_statistic=float(data["ks_statistic"]),
    )



def promote_and_export_model(
    model_eval: ModelEvaluationResult,
    transformer: YeoJohnsonTransformer,
    y_test: pd.Series | np.ndarray,
    test_probs: np.ndarray,
    output_bundle_path: str | Path = DEFAULT_EXPORT_PATH,
    register_in_mlflow: bool = True,
    tracking_uri: str | Path | None = DEFAULT_TRACKING_DIR,
    experiment_name: str = DEFAULT_TRAINING_EXPERIMENT,
    model_name: str = DEFAULT_PROMOTED_MODEL_NAME,
    params: ProjectParams | None = None,
) -> tuple[PromotedModelBundle, PromotionGateResult]:
    """Evaluate candidate model through INV-3 promotion gate, register in MLflow, and export.

    Args:
        model_eval: ModelEvaluationResult for the candidate model.
        transformer: Fitted YeoJohnsonTransformer to bundle for serving.
        y_test: Held-out test labels.
        test_probs: Predicted default probabilities on held-out test data.
        output_bundle_path: Filepath where the serialized bundle is saved.
        register_in_mlflow: Whether to log lineage to MLflow Model Registry.
        tracking_uri: MLflow tracking URI.
        experiment_name: MLflow experiment name.
        model_name: MLflow registered model name.
        params: Project configuration params.

    Returns:
        Tuple of (PromotedModelBundle, PromotionGateResult).

    Raises:
        PromotionGateError: If the model fails the calibration or discrimination check.
    """
    if params is None:
        params = load_params()

    brier_thresh = params.promotion_gate.brier_threshold
    auc_thresh = params.promotion_gate.auc_threshold

    y_true_seq = np.asarray(y_test)
    gate_res = evaluate_promotion_gate(
        y_true=y_true_seq,
        y_prob=test_probs,
        brier_threshold=brier_thresh,
        auc_threshold=auc_thresh,
    )

    if not gate_res.passed:
        brier_val = gate_res.calibration.brier_score
        auc_val = gate_res.discrimination.roc_auc
        raise PromotionGateError(
            f"Model promotion rejected: {gate_res.reason} "
            f"(brier={brier_val:.5f}, auc={auc_val:.4f})"
        )

    bundle = PromotedModelBundle(
        model=model_eval.model,
        transformer=transformer,
        model_family=model_eval.model_family,
        weighted=model_eval.weighted,
        calibration_method=model_eval.calibration_method,
        brier_score=gate_res.calibration.brier_score,
        roc_auc=gate_res.discrimination.roc_auc,
        ks_statistic=model_eval.ks_statistic,
    )

    # Export joblib artifact for lean serving (ADR-022)
    out_path = Path(output_bundle_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_dict = build_promoted_bundle_dict(bundle)
    joblib.dump(bundle_dict, out_path)

    # MLflow Registration (lineage/tracking only per ADR-022)
    if register_in_mlflow and tracking_uri is not None:
        if isinstance(tracking_uri, Path):
            uri_str = tracking_uri.resolve().as_uri()
        elif tracking_uri.startswith(("http://", "https://", "file://", "sqlite:", "postgresql:")):
            uri_str = tracking_uri
        else:
            uri_str = Path(tracking_uri).resolve().as_uri()
        mlflow.set_tracking_uri(uri_str)
        mlflow.set_experiment(experiment_name)

        run_name = f"promotion-{model_eval.model_family}-{model_eval.calibration_method}"
        with mlflow.start_run(run_name=run_name):
            mlflow.set_tags(
                {
                    "phase": "1",
                    "stage": "5",
                    "action": "model_promotion",
                    "promoted_model_name": model_name,
                    "governed_by": "INV-3",
                    "status": "promoted",
                }
            )
            mlflow.log_params(
                {
                    "model_family": model_eval.model_family,
                    "weighted": model_eval.weighted,
                    "calibration_method": model_eval.calibration_method,
                    "brier_threshold": brier_thresh,
                    "auc_threshold": auc_thresh,
                }
            )
            mlflow.log_metrics(
                {
                    "promoted_brier_score": bundle.brier_score,
                    "promoted_roc_auc": bundle.roc_auc,
                    "promoted_ks_statistic": bundle.ks_statistic,
                }
            )
            # Log bundle file as an artifact
            mlflow.log_artifact(str(out_path), artifact_path="model_bundle")

    return bundle, gate_res



def run_stage_5_promotion(
    processed_dir: str | Path = "data/processed",
    transformer_path: str | Path = "artifacts/preprocessor.joblib",
    output_bundle_path: str | Path = DEFAULT_EXPORT_PATH,
    register_in_mlflow: bool = True,
    tracking_uri: str | Path | None = DEFAULT_TRACKING_DIR,
    experiment_name: str = DEFAULT_TRAINING_EXPERIMENT,
) -> tuple[PromotedModelBundle, PromotionGateResult]:
    """Execute Stage 5 promotion pipeline using Stage 3's winning model configuration."""
    params = load_params()
    transformer = load_transformer(transformer_path)
    X_tr, X_te, y_tr, y_te = load_processed_data(processed_dir=processed_dir)

    pos_count = float(y_tr.sum())
    total_count = float(len(y_tr))
    pos_weight = (total_count - pos_count) / pos_count

    # Stage 3 Winner: XGBoost unweighted isotonic calibration
    winner_eval = train_and_evaluate_config(
        X_train=X_tr,
        y_train=y_tr,
        X_test=X_te,
        y_test=y_te,
        model_family="xgboost",
        weighted=False,
        calibration_method="isotonic",
        params=params,
        pos_weight=pos_weight,
    )

    test_probs = winner_eval.model.predict_proba(X_te)[:, 1]

    bundle, gate_res = promote_and_export_model(
        model_eval=winner_eval,
        transformer=transformer,
        y_test=y_te,
        test_probs=test_probs,
        output_bundle_path=output_bundle_path,
        register_in_mlflow=register_in_mlflow,
        tracking_uri=tracking_uri,
        experiment_name=experiment_name,
        params=params,
    )
    return bundle, gate_res


def main() -> None:
    """CLI entrypoint for Stage 5 model promotion."""
    parser = argparse.ArgumentParser(description="ACRAS Stage 5: Model Promotion & Freezing")
    parser.add_argument(
        "--processed-dir",
        default="data/processed",
        help="Directory containing preprocessed parquet partitions",
    )
    parser.add_argument(
        "--transformer-path",
        default="artifacts/preprocessor.joblib",
        help="Path to fitted transformer artifact",
    )
    parser.add_argument(
        "--output-bundle",
        default=DEFAULT_EXPORT_PATH,
        help="Path to export the frozen joblib bundle",
    )
    parser.add_argument(
        "--tracking-uri",
        default=DEFAULT_TRACKING_DIR,
        help="Path/URI to MLflow tracking store",
    )
    args = parser.parse_args()

    print("[promote] Initiating Stage 5 promotion of Stage 3 winning candidate...")
    try:
        bundle, gate_res = run_stage_5_promotion(
            processed_dir=args.processed_dir,
            transformer_path=args.transformer_path,
            output_bundle_path=args.output_bundle,
            register_in_mlflow=True,
            tracking_uri=args.tracking_uri,
        )
    except PromotionGateError as exc:
        print(f"[promote] FATAL: Promotion blocked by INV-3 gate:\n  {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"[promote] ERROR during promotion execution: {exc}", file=sys.stderr)
        sys.exit(2)

    print("\n[promote] SUCCESS: Model Promoted to Serving & Frozen Artifact Exported!")
    print(
        f"  Model Family:       {bundle.model_family}\n"
        f"  Calibration Method: {bundle.calibration_method}\n"
        f"  Class Weighted:     {bundle.weighted}\n"
        f"  Brier Score:        {bundle.brier_score:.6f} (Gate: <= 0.030)\n"
        f"  ROC-AUC:            {bundle.roc_auc:.6f} (Gate: >= 0.850)\n"
        f"  KS Statistic:       {bundle.ks_statistic:.6f}\n"
        f"  Exported Bundle:    {args.output_bundle}\n"
        f"  Gate Verdict:       {gate_res.reason}"
    )


if __name__ == "__main__":
    main()

