"""Model Training, Cross-Validated Calibration, and Experiment Tracking.

Governed by:
    INV-1 (ADR-001): Deterministic core; no LLM outputs involved in calculation.
    INV-3 (ADR-003): Promotion requires calibration gate (Brier score) first,
        discrimination (AUC/KS) second. Strong AUC alone is never sufficient.
    ADR-010: Structural separation of training (pipelines/training/) from serving (tier1_ml/).
    ADR-017 (D-1.1): Three candidate models (XGBoost, LightGBM, LogisticRegression baseline).
    ADR-018 (D-1.2): 5-fold cross-validated calibration (CalibratedClassifierCV) on train split.
    ADR-019 (D-1.3): Class weighting vs unweighted empirical comparison.
    ADR-020 (D-1.4): Empirical comparison of Platt scaling (sigmoid) vs Isotonic regression.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import lightgbm as lgb
import mlflow
import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import ks_2samp
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

from src.config.loader import ProjectParams, load_params
from src.pipelines.feature.split import load_processed_data

DEFAULT_TRAINING_EXPERIMENT: str = "acras-model-training"
DEFAULT_TRACKING_DIR: str = "./mlruns"


@dataclass(frozen=True)
class ModelEvaluationResult:
    """Evaluation metrics and artifacts for a single trained model configuration."""

    model_family: str
    weighted: bool
    calibration_method: str
    brier_score: float
    roc_auc: float
    ks_statistic: float
    prob_true: list[float]
    prob_pred: list[float]
    model: CalibratedClassifierCV


@dataclass(frozen=True)
class TrainingSummary:
    """Summary of all evaluated configurations and winning candidate."""

    results: list[ModelEvaluationResult]
    winner: ModelEvaluationResult


def instantiate_base_estimator(
    model_family: str,
    weighted: bool,
    params: ProjectParams,
    pos_weight: float,
) -> Any:
    """Instantiate uncalibrated base estimator with specific hyperparams and weighting."""
    if model_family == "logistic_regression":
        class_weight = "balanced" if weighted else None
        lr_cfg = params.models["logistic_regression"]
        return LogisticRegression(
            max_iter=int(lr_cfg["max_iter"]),
            solver=str(lr_cfg["solver"]),
            C=float(lr_cfg["C"]),
            class_weight=class_weight,
            random_state=params.seed,
        )
    elif model_family == "lightgbm":
        scale_pos_weight = pos_weight if weighted else 1.0
        lgb_cfg = params.models["lightgbm"]
        return lgb.LGBMClassifier(
            n_estimators=int(lgb_cfg["n_estimators"]),
            learning_rate=float(lgb_cfg["learning_rate"]),
            max_depth=int(lgb_cfg["max_depth"]),
            num_leaves=int(lgb_cfg["num_leaves"]),
            random_state=int(lgb_cfg["random_state"]),
            n_jobs=int(lgb_cfg["n_jobs"]),
            verbose=int(lgb_cfg["verbose"]),
            scale_pos_weight=scale_pos_weight,
        )
    elif model_family == "xgboost":
        scale_pos_weight = pos_weight if weighted else 1.0
        xgb_cfg = params.models["xgboost"]
        return xgb.XGBClassifier(
            n_estimators=int(xgb_cfg["n_estimators"]),
            learning_rate=float(xgb_cfg["learning_rate"]),
            max_depth=int(xgb_cfg["max_depth"]),
            subsample=float(xgb_cfg["subsample"]),
            colsample_bytree=float(xgb_cfg["colsample_bytree"]),
            random_state=params.seed,
            scale_pos_weight=scale_pos_weight,
            eval_metric="logloss",
        )
    else:
        raise ValueError(f"Unknown model family: {model_family}")



def train_and_evaluate_config(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    model_family: str,
    weighted: bool,
    calibration_method: str,
    params: ProjectParams,
    pos_weight: float,
) -> ModelEvaluationResult:
    """Train, cross-validate calibrate, and evaluate a single configuration."""
    base_est = instantiate_base_estimator(
        model_family=model_family,
        weighted=weighted,
        params=params,
        pos_weight=pos_weight,
    )

    # 5-fold cross-validated calibration (ADR-018 & ADR-020)
    calibrator = CalibratedClassifierCV(
        estimator=base_est,
        method=calibration_method,
        cv=params.cv.n_splits,
    )
    calibrator.fit(X_train, y_train)

    # Predict calibrated default probabilities on held-out test set
    probs = calibrator.predict_proba(X_test)[:, 1]

    # Metrics computation
    brier = float(brier_score_loss(y_test, probs))
    auc = float(roc_auc_score(y_test, probs))
    pos_probs = probs[y_test == 1]
    neg_probs = probs[y_test == 0]
    ks_res: Any = ks_2samp(pos_probs, neg_probs)
    ks_stat = float(ks_res.statistic)

    prob_true_arr, prob_pred_arr = calibration_curve(y_test, probs, n_bins=5)
    prob_true = [float(x) for x in prob_true_arr]
    prob_pred = [float(x) for x in prob_pred_arr]

    return ModelEvaluationResult(
        model_family=model_family,
        weighted=weighted,
        calibration_method=calibration_method,
        brier_score=brier,
        roc_auc=auc,
        ks_statistic=ks_stat,
        prob_true=prob_true,
        prob_pred=prob_pred,
        model=calibrator,
    )



def train_and_evaluate_all_models(
    processed_dir: str | Path = "data/processed",
    tracking_uri: str | Path | None = DEFAULT_TRACKING_DIR,
    experiment_name: str = DEFAULT_TRAINING_EXPERIMENT,
    params: ProjectParams | None = None,
    log_to_mlflow: bool = True,
) -> TrainingSummary:
    """Train all 12 candidate model configurations and identify the winner.

    Selects best configuration by Brier score first (INV-3 / ADR-003),
    using AUC only as a tiebreaker.
    """
    if params is None:
        params = load_params()

    X_train, X_test, y_train, y_test = load_processed_data(processed_dir=processed_dir)
    pos_count = float(y_train.sum())
    total_count = float(len(y_train))
    pos_weight = (total_count - pos_count) / pos_count

    if log_to_mlflow and tracking_uri is not None:
        if isinstance(tracking_uri, Path):
            uri_str = tracking_uri.resolve().as_uri()
        elif tracking_uri.startswith(("http://", "https://", "file://", "sqlite:", "postgresql:")):
            uri_str = tracking_uri
        else:
            uri_str = Path(tracking_uri).resolve().as_uri()
        mlflow.set_tracking_uri(uri_str)
        mlflow.set_experiment(experiment_name)

    model_families = ["logistic_regression", "lightgbm", "xgboost"]
    weightings = [False, True]
    calibration_methods = params.calibration.methods

    results: list[ModelEvaluationResult] = []

    for model_family in model_families:
        for weighted in weightings:
            for cal_method in calibration_methods:
                run_name = f"{model_family}-{'weighted' if weighted else 'unweighted'}-{cal_method}"
                result = train_and_evaluate_config(
                    X_train=X_train,
                    y_train=y_train,
                    X_test=X_test,
                    y_test=y_test,
                    model_family=model_family,
                    weighted=weighted,
                    calibration_method=cal_method,
                    params=params,
                    pos_weight=pos_weight,
                )
                results.append(result)

                if log_to_mlflow:
                    with mlflow.start_run(run_name=run_name):
                        mlflow.set_tags(
                            {
                                "phase": "1",
                                "stage": "3",
                                "model_family": model_family,
                                "weighted": str(weighted),
                                "calibration_method": cal_method,
                                "governed_by": "INV-3",
                            }
                        )
                        mlflow.log_params(
                            {
                                "model_family": model_family,
                                "weighted": weighted,
                                "calibration_method": cal_method,
                                "cv_folds": params.cv.n_splits,
                                "pos_weight_value": pos_weight if weighted else 1.0,
                            }
                        )
                        mlflow.log_metrics(
                            {
                                "brier_score": result.brier_score,
                                "roc_auc": result.roc_auc,
                                "ks_statistic": result.ks_statistic,
                            }
                        )

    # Sort strictly by Brier score ascending (calibration first), AUC descending (tiebreaker)
    sorted_results = sorted(results, key=lambda r: (r.brier_score, -r.roc_auc))
    winner = sorted_results[0]

    return TrainingSummary(
        results=sorted_results,
        winner=winner,
    )


def save_leaderboard_csv(
    summary: TrainingSummary,
    output_path: str | Path = "reports/model_leaderboard.csv",
) -> Path:
    """Save the model evaluation leaderboard to a CSV file for traceability.

    Args:
        summary: TrainingSummary containing ordered evaluation results.
        output_path: Destination path for the CSV artifact.

    Returns:
        Path to the saved CSV file.
    """
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for rank, r in enumerate(summary.results, start=1):
        rows.append(
            {
                "rank": rank,
                "model_family": r.model_family,
                "weighted": r.weighted,
                "calibration_method": r.calibration_method,
                "brier_score": round(r.brier_score, 6),
                "roc_auc": round(r.roc_auc, 6),
                "ks_statistic": round(r.ks_statistic, 6),
            }
        )
    df_leaderboard = pd.DataFrame(rows)
    df_leaderboard.to_csv(out_p, index=False)
    return out_p




def run_label_shuffle_falsification(
    processed_dir: str | Path = "data/processed",
    params: ProjectParams | None = None,
    seed: int = 12345,
) -> ModelEvaluationResult:
    """Train throwaway configuration on randomly shuffled training labels.

    Falsification test for Stage 3:
    If a model trained on shuffled labels achieves good AUC (>0.65) or good calibration,
    it reveals upstream data leakage (e.g. from Stage 2) that legitimate models could mask.
    """
    if params is None:
        params = load_params()

    X_train, X_test, y_train, y_test = load_processed_data(processed_dir=processed_dir)

    # Permute training labels randomly
    rng = np.random.default_rng(seed)
    y_values = np.asarray(y_train.to_numpy())
    y_train_shuffled = pd.Series(
        rng.permutation(y_values),
        index=y_train.index,
    )

    pos_count = float(y_train_shuffled.sum())
    total_count = float(len(y_train_shuffled))
    pos_weight = (total_count - pos_count) / pos_count

    # Evaluate throwaway LogisticRegression model
    result = train_and_evaluate_config(
        X_train=X_train,
        y_train=y_train_shuffled,
        X_test=X_test,
        y_test=y_test,
        model_family="logistic_regression",
        weighted=False,
        calibration_method="sigmoid",
        params=params,
        pos_weight=pos_weight,
    )
    return result


def main() -> None:
    """CLI entrypoint for executing Stage 3 model training pipeline."""
    parser = argparse.ArgumentParser(description="ACRAS Stage 3: Model Training & Calibration")
    parser.add_argument(
        "--processed-dir",
        default="data/processed",
        help="Directory containing preprocessed parquet partitions",
    )
    parser.add_argument(
        "--tracking-uri",
        default=DEFAULT_TRACKING_DIR,
        help="Path/URI to MLflow tracking store",
    )
    parser.add_argument(
        "--experiment-name",
        default=DEFAULT_TRAINING_EXPERIMENT,
        help="MLflow experiment name",
    )
    parser.add_argument(
        "--output-csv",
        default="reports/model_leaderboard.csv",
        help="Path to save leaderboard CSV artifact (default: reports/model_leaderboard.csv)",
    )

    args = parser.parse_args()

    print(
        "[train_pipeline] Initiating Stage 3 model training across 12 candidate configurations..."
    )
    summary = train_and_evaluate_all_models(
        processed_dir=args.processed_dir,
        tracking_uri=args.tracking_uri,
        experiment_name=args.experiment_name,
        log_to_mlflow=True,
    )

    print("\n--- Model Training & Calibration Leaderboard (Calibration First: Brier ASC) ---")
    print(f"{'Model':<20} {'Weighted':<10} {'Cal Method':<12} {'Brier':<10} {'AUC':<10} {'KS':<10}")
    print("-" * 74)
    for r in summary.results:
        w_str = "Yes" if r.weighted else "No"
        print(
            f"{r.model_family:<20} {w_str:<10} {r.calibration_method:<12} "
            f"{r.brier_score:<10.5f} {r.roc_auc:<10.4f} {r.ks_statistic:<10.4f}"
        )

    w = summary.winner
    print("\n[train_pipeline] Stage 3 Winner Selected:")
    print(
        f"  Model Family:       {w.model_family}\n"
        f"  Class Weighted:     {w.weighted}\n"
        f"  Calibration Method: {w.calibration_method}\n"
        f"  Brier Score:        {w.brier_score:.5f}\n"
        f"  ROC-AUC:            {w.roc_auc:.4f}\n"
        f"  KS Statistic:       {w.ks_statistic:.4f}"
    )

    if args.output_csv:
        csv_path = save_leaderboard_csv(summary, output_path=args.output_csv)
        print(f"\n[train_pipeline] Saved model leaderboard CSV to: {csv_path}")


    print("\n[train_pipeline] Running label-shuffle falsification test...")
    shuffled_res = run_label_shuffle_falsification(processed_dir=args.processed_dir)
    print(
        f"  Shuffled Model AUC:   {shuffled_res.roc_auc:.4f} (near chance ~0.50 expected)\n"
        f"  Shuffled Brier Score: {shuffled_res.brier_score:.5f}"
    )
    if shuffled_res.roc_auc > 0.65:
        print(
            "[train_pipeline] WARNING: Shuffled AUC unexpectedly high! Inspect data pipeline.",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        print("[train_pipeline] PASS: Falsification verified (no target leakage detected).")


if __name__ == "__main__":
    main()

