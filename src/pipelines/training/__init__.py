"""Training Pipeline Module.

Scope: FTI Training stage responsible for feature ingestion, model training,
calibration verification (Brier score / reliability curve), and model artifact registration.

Architectural Invariant (INV-7 & ADR-010):
This module produces the frozen model artifact registered for serving.
Training code and serving code (`src/tier1_ml/`) are strictly separated.
All training runs must be gated by Great Expectations data contracts.
"""

from src.pipelines.training.promote import (
    DEFAULT_EXPORT_PATH,
    DEFAULT_PROMOTED_MODEL_NAME,
    PromotedModelBundle,
    PromotionGateError,
    load_promoted_bundle,
    promote_and_export_model,
    run_stage_5_promotion,
)
from src.pipelines.training.promotion_gate import (
    CalibrationCheckResult,
    DiscriminationCheckResult,
    PromotionGateResult,
    check_calibration,
    check_discrimination,
    evaluate_promotion_gate,
)
from src.pipelines.training.rating_mapping import map_pd_to_credit_rating
from src.pipelines.training.train import (
    DEFAULT_TRACKING_DIR,
    DEFAULT_TRAINING_EXPERIMENT,
    ModelEvaluationResult,
    TrainingSummary,
    run_label_shuffle_falsification,
    save_leaderboard_csv,
    train_and_evaluate_all_models,
    train_and_evaluate_config,
)

__all__ = [
    "DEFAULT_EXPORT_PATH",
    "DEFAULT_PROMOTED_MODEL_NAME",
    "PromotedModelBundle",
    "PromotionGateError",
    "load_promoted_bundle",
    "map_pd_to_credit_rating",
    "promote_and_export_model",
    "run_stage_5_promotion",

    "CalibrationCheckResult",
    "DEFAULT_TRACKING_DIR",
    "DEFAULT_TRAINING_EXPERIMENT",
    "DiscriminationCheckResult",
    "ModelEvaluationResult",
    "PromotionGateResult",
    "TrainingSummary",
    "check_calibration",
    "check_discrimination",
    "evaluate_promotion_gate",
    "run_label_shuffle_falsification",
    "save_leaderboard_csv",
    "train_and_evaluate_all_models",
    "train_and_evaluate_config",
]


