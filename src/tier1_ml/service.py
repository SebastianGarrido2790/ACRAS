"""Tier 1 ML Service Engine.

Governed by:
    INV-1 (ADR-001): Pure deterministic scoring; zero LLM output in calculations.
    ADR-010: Pure serving logic decoupled from training code. Zero MLflow dependency.
    ADR-022: Loads lean joblib bundle at startup.
    ADR-025: Uses bundled fitted Yeo-Johnson transformer to ensure 100% training-serving parity.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from src.config.loader import load_params
from src.schemas.features import CANONICAL_FEATURES
from src.tier1_ml.rating import map_pd_to_credit_rating
from src.tier1_ml.schemas import InferenceRequest, InferenceResponse

DEFAULT_BUNDLE_PATH: str = "artifacts/promoted_model_bundle.joblib"


class Tier1ModelService:
    """Inference engine for Tier 1 Calibrated Probability of Default predictions."""

    def __init__(self, bundle_path: str | Path = DEFAULT_BUNDLE_PATH) -> None:
        """Initialize the model service by loading the serialized joblib bundle.

        Args:
            bundle_path: Path to promoted_model_bundle.joblib.

        Raises:
            FileNotFoundError: If the bundle artifact is not found.
            ValueError: If the bundle structure or contents are corrupted.
        """
        self.bundle_path = Path(bundle_path)
        if not self.bundle_path.is_file():
            raise FileNotFoundError(
                f"Promoted model bundle not found at: {self.bundle_path.resolve()}"
            )

        data: Any = joblib.load(self.bundle_path)
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict bundle, got {type(data).__name__}")

        self.model = data["model"]
        self.transformer = data["transformer"]
        self.model_family = str(data.get("model_family", "xgboost"))
        self.calibration_method = str(data.get("calibration_method", "isotonic"))
        self.brier_score = float(data.get("brier_score", 0.0))
        self.roc_auc = float(data.get("roc_auc", 0.0))

        # Pre-load rating thresholds from config
        self.params = load_params()
        self.thresholds = self.params.rating_thresholds

    def predict(self, request: InferenceRequest) -> InferenceResponse:
        """Score an incoming request and return calibrated PD and rating.

        Args:
            request: Validated InferenceRequest with 94 canonical features.

        Returns:
            InferenceResponse containing calibrated PD and credit rating.
        """
        # 1. Arrange canonical features in exact canonical ordering
        raw_row = [request.raw_features[col] for col in CANONICAL_FEATURES]
        df_input = pd.DataFrame([raw_row], columns=pd.Index(CANONICAL_FEATURES))

        # 2. Apply Yeo-Johnson transform for explicit training-serving parity (ADR-025)
        df_transformed = self.transformer.transform(df_input)

        # 3. Model predict calibrated default probability
        probs = self.model.predict_proba(df_transformed.values)
        pd_val = float(probs[0, 1])

        # Clamp to [0.0, 1.0] for absolute numerical safety
        pd_clamped = max(0.0, min(1.0, pd_val))

        # 4. Map PD to discrete credit rating (ADR-021 / PRD FR4)
        rating = map_pd_to_credit_rating(pd_clamped, self.thresholds)

        return InferenceResponse(
            company_id=request.company_id,
            pd=round(pd_clamped, 6),
            credit_rating=rating,
            model_family=self.model_family,
            calibration_method=self.calibration_method,
            model_version="v1",
        )
