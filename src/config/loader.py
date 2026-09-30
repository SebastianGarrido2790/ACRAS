"""Configuration loader and schemas for params.yaml.

Provides strongly-typed models and a loader function for accessing project parameters
without inline magic numbers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class SplitConfig(BaseModel):
    """Dataset splitting parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    test_size: float = Field(gt=0.0, lt=1.0)
    stratify: bool = True


class CVConfig(BaseModel):
    """Cross-validation parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    n_splits: int = Field(ge=2)
    shuffle: bool = True


class PreprocessingConfig(BaseModel):
    """Feature preprocessing parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    method: str = "yeo-johnson"
    standardize: bool = True


class ImbalanceConfig(BaseModel):
    """Class imbalance handling configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    use_class_weights: bool = True


class CalibrationConfig(BaseModel):
    """Post-hoc probability calibration parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    methods: list[str]


class PromotionGateConfig(BaseModel):
    """Model promotion gate threshold parameters (INV-3 / FR12)."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    brier_threshold: float = Field(gt=0.0, lt=1.0)
    auc_threshold: float = Field(gt=0.5, lt=1.0)

class RatingThreshold(BaseModel):
    """Discrete credit rating bracket bound."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    rating: str
    max_pd: float = Field(ge=0.0, le=1.0)


class ProjectParams(BaseModel):
    """Root configuration object loaded from params.yaml."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    seed: int
    split: SplitConfig
    cv: CVConfig
    preprocessing: PreprocessingConfig
    imbalance: ImbalanceConfig
    calibration: CalibrationConfig
    models: dict[str, dict[str, Any]]
    promotion_gate: PromotionGateConfig

    rating_thresholds: list[RatingThreshold]


def load_params(params_path: Path | str = "params.yaml") -> ProjectParams:
    """Load and validate parameters from a YAML file.

    Args:
        params_path: Path to the params.yaml file (default: params.yaml at repo root).

    Returns:
        Validated ProjectParams instance.

    Raises:
        FileNotFoundError: If the specified config file does not exist.
        ValueError: If parsing or validation fails.
    """
    path = Path(params_path)
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path.resolve()}")

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}, got {type(data).__name__}")

    return ProjectParams.model_validate(data)
