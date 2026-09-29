"""Unit tests for params.yaml and configuration loader."""

from pathlib import Path

import pytest

from src.config.loader import ProjectParams, load_params


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
