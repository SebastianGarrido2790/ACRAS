"""Unit tests for Stage 2 Feature Pipeline: Preprocessing & Split.

Governed by:
    D-1.2 (ADR-018): Stratified train/test split holding out test set completely.
    D-1.10 (ADR-024): Duplicate feature column exclusion.
    D-1.11 (ADR-025): Yeo-Johnson fit on train set only (no data leakage).
    D-1.12 (ADR-026): Outliers untouched (zero row deletions).

Stage 2 Falsifications:
    1. Stratification test: Positive class ratio matches ~3.226% across train, test, and 5 CV folds.
    2. Data leakage test: Parameters fit on train portion differ from fit on full dataset.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.config.loader import load_params
from src.pipelines.feature.split import (
    load_processed_data,
    load_transformer,
    prepare_and_split_data,
)
from src.pipelines.feature.transform import YeoJohnsonTransformer
from src.schemas.features import (
    CANONICAL_FEATURES,
    DROPPED_DUPLICATE_FEATURE,
    TARGET_COLUMN,
)


@pytest.fixture(scope="module")
def raw_data_path() -> Path:
    """Fixture returning path to raw dataset if present."""
    p = Path("data/raw/data.csv")
    if not p.exists():
        pytest.skip("data/raw/data.csv not found (DVC-tracked)")
    return p


def test_stratification_falsification(raw_data_path: Path, tmp_path: Path) -> None:
    """Falsification 1: Verify stratification across train, test, and 5 CV folds.

    Tolerance is checked against overall ~3.226% positive ratio.
    """
    params = load_params()
    df_raw = pd.read_csv(raw_data_path)
    overall_ratio = float(df_raw[TARGET_COLUMN].mean())
    expected_positive_count = int(df_raw[TARGET_COLUMN].sum())
    assert expected_positive_count == 220
    assert abs(overall_ratio - 0.03226) < 1e-4

    artifacts = prepare_and_split_data(
        raw_data_path=raw_data_path,
        params=params,
        output_dir=tmp_path / "processed",
        artifact_dir=tmp_path / "artifacts",
    )

    # Train ratio check
    assert abs(artifacts.train_positive_ratio - overall_ratio) < 1e-4
    # Test ratio check
    assert abs(artifacts.test_positive_ratio - overall_ratio) < 1e-4

    # Check 5 CV fold ratios within training portion
    assert len(artifacts.fold_positive_ratios) == params.cv.n_splits
    for fold_ratio in artifacts.fold_positive_ratios:
        # Every fold should maintain ~3.2% ratio (approx 35-36 positives per fold)
        assert abs(fold_ratio - overall_ratio) < 0.002


def test_data_leakage_falsification(raw_data_path: Path, tmp_path: Path) -> None:
    """Falsification 2: Prove Yeo-Johnson transformer does not leak.

    Fitting strictly on X_train MUST yield distinct parameters compared
    to fitting on the full dataset (X_train + X_test).
    """
    params = load_params()
    df_raw = pd.read_csv(raw_data_path)
    X_full = df_raw[list(CANONICAL_FEATURES)].copy()

    # Run train-only split & fit
    artifacts = prepare_and_split_data(
        raw_data_path=raw_data_path,
        params=params,
        output_dir=tmp_path / "processed",
        artifact_dir=tmp_path / "artifacts",
    )

    # Refit throwaway transformer on FULL dataset
    full_transformer = YeoJohnsonTransformer(
        standardize=params.preprocessing.standardize,
        feature_names=CANONICAL_FEATURES,
    )
    full_transformer.fit(pd.DataFrame(X_full))

    train_lambdas = artifacts.transformer.pt.lambdas_
    full_lambdas = full_transformer.pt.lambdas_

    # Prove parameters are NOT identical (they must differ if fit on train only)
    lambda_diff = np.abs(train_lambdas - full_lambdas)
    max_diff = float(np.max(lambda_diff))
    mean_diff = float(np.mean(lambda_diff))
    differing_features = int(np.sum(lambda_diff > 1e-5))

    assert not np.array_equal(train_lambdas, full_lambdas)
    assert max_diff > 10.0
    assert mean_diff > 1.0
    assert differing_features > 50


def test_duplicate_feature_absence_and_schema(raw_data_path: Path, tmp_path: Path) -> None:
    """Gate 2: Verify duplicate column absent and canonical feature schema enforced."""
    params = load_params()
    artifacts = prepare_and_split_data(
        raw_data_path=raw_data_path,
        params=params,
        output_dir=tmp_path / "processed",
        artifact_dir=tmp_path / "artifacts",
    )

    # Shapes match 80/20 split of 6819 rows
    assert artifacts.X_train.shape == (5455, 94)
    assert artifacts.X_test.shape == (1364, 94)
    assert len(artifacts.y_train) == 5455
    assert len(artifacts.y_test) == 1364

    # Duplicate column is strictly absent
    assert DROPPED_DUPLICATE_FEATURE not in artifacts.X_train.columns
    assert DROPPED_DUPLICATE_FEATURE not in artifacts.X_test.columns
    assert list(artifacts.X_train.columns) == list(CANONICAL_FEATURES)
    assert list(artifacts.X_test.columns) == list(CANONICAL_FEATURES)

    # Outliers untouched: zero rows dropped
    assert len(artifacts.X_train) + len(artifacts.X_test) == 6819


def test_load_persisted_artifacts(tmp_path: Path, raw_data_path: Path) -> None:
    """Gate 2: Verify persisted parquet partitions and joblib transformer reload accurately."""
    params = load_params()
    out_dir = tmp_path / "processed"
    art_dir = tmp_path / "artifacts"

    artifacts = prepare_and_split_data(
        raw_data_path=raw_data_path,
        params=params,
        output_dir=out_dir,
        artifact_dir=art_dir,
    )

    X_tr, X_te, y_tr, y_te = load_processed_data(processed_dir=out_dir)
    transformer = load_transformer(artifact_path=art_dir / "preprocessor.joblib")

    assert X_tr.shape == artifacts.X_train.shape
    assert X_te.shape == artifacts.X_test.shape
    assert y_tr.equals(artifacts.y_train)
    assert y_te.equals(artifacts.y_test)
    assert np.allclose(X_tr.values, artifacts.X_train.values)
    assert np.array_equal(transformer.pt.lambdas_, artifacts.transformer.pt.lambdas_)
