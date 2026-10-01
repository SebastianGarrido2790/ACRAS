"""Inference Request and Response Schemas for Tier 1 ML Service.

Governed by:
    D-1.8 (ADR-023): Thin request wrapper schema with runtime key validation
        against the single canonical feature list.
    D-1.10 (ADR-024): Exact duplicate column permanently excluded from canonical schema.
    INV-2 (ADR-002): Pydantic contract boundaries; extra fields strictly forbidden.
"""

from __future__ import annotations

import math
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schemas.features import CANONICAL_FEATURES, DROPPED_DUPLICATE_FEATURE


class InferenceRequest(BaseModel):
    """Inference request schema matching the evidence bundle shape."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: Annotated[
        str,
        Field(min_length=1, description="Unique company identifier (e.g. COMP-0042)"),
    ]
    raw_features: Annotated[
        dict[str, float | int],
        Field(description="Mapping of canonical feature names to raw numerical values"),
    ]

    @field_validator("raw_features")
    @classmethod
    def validate_canonical_features(
        cls, v: dict[str, float | int]
    ) -> dict[str, float | int]:
        """Validate that raw_features matches the canonical 94-feature list exactly."""
        if not isinstance(v, dict):
            raise ValueError("raw_features must be a dictionary")

        provided_keys = set(v.keys())
        canonical_keys = set(CANONICAL_FEATURES)

        # Check for forbidden duplicate column specifically (ADR-024)
        if DROPPED_DUPLICATE_FEATURE in provided_keys:
            raise ValueError(
                f"Forbidden duplicate feature '{DROPPED_DUPLICATE_FEATURE}' provided. "
                "Feature was eliminated per ADR-024."
            )

        # Check for missing keys
        missing = canonical_keys - provided_keys
        if missing:
            sample_missing = sorted(list(missing))[:5]
            raise ValueError(
                f"Request is missing {len(missing)} required canonical features: {sample_missing}"
            )

        # Check for unexpected extra keys
        extra = provided_keys - canonical_keys
        if extra:
            sample_extra = sorted(list(extra))[:5]
            raise ValueError(
                f"Request contains {len(extra)} unexpected extra features: {sample_extra}"
            )

        # Check for NaN / Inf values
        for key, val in v.items():
            if val is None or not isinstance(val, (int, float)) or (
                math.isnan(val) or math.isinf(val)
            ):
                raise ValueError(f"Feature '{key}' must be a finite number, got {val}")

        return v


class InferenceResponse(BaseModel):
    """Prediction response schema aligned to the EvidenceBundle PD and credit_rating fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: str = Field(description="Unique company identifier")
    pd: float = Field(ge=0.0, le=1.0, description="Calibrated Probability of Default")
    credit_rating: str = Field(description="Derived credit rating bracket e.g. AAA, BB")
    model_family: str = Field(description="Underlying promoted model family")
    calibration_method: str = Field(description="Post-hoc calibration method applied")
    model_version: str = Field(default="v1", description="Serving model version")
