"""Unit tests for params.yaml and configuration loader."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config.loader import ProjectParams, SimulationConfig, load_params


def test_load_params_success() -> None:
    """Verify loading the real params.yaml file."""
    params = load_params("params.yaml")
    assert isinstance(params, ProjectParams)

    # Core parameters
    assert params.seed == 42
    assert params.split.test_size == 0.20
    assert params.split.stratify is True
    assert params.cv.n_splits == 5
    assert params.cv.shuffle is True
    assert params.preprocessing.method == "yeo-johnson"
    assert params.imbalance.use_class_weights is True

    # Calibration methods
    assert "sigmoid" in params.calibration.methods
    assert "isotonic" in params.calibration.methods

    # Models present
    assert "logistic_regression" in params.models
    assert "lightgbm" in params.models
    assert "xgboost" in params.models

    # Rating thresholds monotonic and bounded
    thresholds = params.rating_thresholds
    assert len(thresholds) >= 5
    assert thresholds[0].rating == "AAA"
    assert thresholds[-1].max_pd == 1.0
    for i in range(len(thresholds) - 1):
        assert thresholds[i].max_pd < thresholds[i + 1].max_pd


def test_load_params_includes_simulation_config() -> None:
    """Verify the Monte Carlo simulation block is populated and bounded."""
    params = load_params("params.yaml")

    assert isinstance(params.simulation, SimulationConfig)
    assert params.simulation.n_iterations == 10_000
    assert params.simulation.seed == 42
    assert params.simulation.asset_correlation == 0.15
    assert params.simulation.tolerance_p10 == 0.015
    assert params.simulation.tolerance_p50 == 0.015
    assert params.simulation.tolerance_p90 == 0.020
    assert params.simulation.latency_budget_ms == 5.0
    assert params.simulation.macro_volatility == 0.20
    assert params.simulation.debt_service_shock_std == 0.15
    assert params.simulation.asset_haircut_std == 0.10


def test_load_params_invalid_simulation_value(tmp_path: Path) -> None:
    """Verify invalid simulation bounds are rejected immediately."""
    bad_yaml = tmp_path / "bad_simulation.yaml"
    bad_yaml.write_text(
        """
seed: 42

split:
  test_size: 0.20
  stratify: true

cv:
  n_splits: 5
  shuffle: true

preprocessing:
  method: "yeo-johnson"
  standardize: true

imbalance:
  use_class_weights: true

calibration:
  methods:
    - "sigmoid"
    - "isotonic"

promotion_gate:
  brier_threshold: 0.030
  auc_threshold: 0.850

models:
  logistic_regression:
    max_iter: 1000
    solver: "lbfgs"
    C: 1.0

simulation:
  n_iterations: -100
  seed: 42
  asset_correlation: 0.15
  tolerance_p10: 0.015
  tolerance_p50: 0.015
  tolerance_p90: 0.020
  latency_budget_ms: 5.0
  macro_volatility: 0.20
  debt_service_shock_std: 0.15
  asset_haircut_std: 0.10

rating_thresholds:
  - rating: "AAA"
    max_pd: 0.001
  - rating: "AA"
    max_pd: 0.0025
  - rating: "A"
    max_pd: 0.005
  - rating: "BBB"
    max_pd: 0.015
  - rating: "BB"
    max_pd: 0.050
  - rating: "B"
    max_pd: 0.150
  - rating: "CCC/C"
    max_pd: 1.000
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_params(bad_yaml)


def test_load_params_file_not_found() -> None:
    """Verify error on nonexistent params path."""
    with pytest.raises(FileNotFoundError):
        load_params("nonexistent_params.yaml")


def test_load_params_invalid_yaml(tmp_path: Path) -> None:
    """Verify error on invalid yaml structure."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("invalid_list:\n  - 1\n  - 2\n", encoding="utf-8")
    with pytest.raises(Exception):
        load_params(bad_yaml)
