"""Unit tests for the YeoJohnsonTransformer preprocessing module."""

import numpy as np
import pandas as pd
import pytest

from src.pipelines.feature.transform import YeoJohnsonTransformer
from src.schemas.features import CANONICAL_FEATURES, DROPPED_DUPLICATE_FEATURE


@pytest.fixture
def sample_feature_names() -> list[str]:
    """Sample list of 5 test features."""
    return [
        "feature_skewed_pos",
        "feature_skewed_neg",
        "feature_normal",
        "feature_with_negatives",
        "feature_zeros",
    ]


@pytest.fixture
def synthetic_data(sample_feature_names: list[str]) -> pd.DataFrame:
    """Create synthetic data exhibiting heavy skewness and negative values."""
    np.random.seed(42)
    n = 200

    # Lognormal (heavily right-skewed positive)
    pos_skew = np.random.lognormal(mean=0.0, sigma=1.5, size=n)

    # Inverted lognormal (heavily left-skewed)
    neg_skew = -np.random.lognormal(mean=0.0, sigma=1.5, size=n)

    # Standard normal
    normal = np.random.normal(loc=0.0, scale=1.0, size=n)

    # Skewed distribution crossing zero (testing Yeo-Johnson's negative handling per D-1.11)
    crossing_zero = np.random.exponential(scale=2.0, size=n) - 1.5

    # Sparse features with zeros
    zeros = np.where(np.random.rand(n) > 0.3, np.random.uniform(0.1, 5.0, size=n), 0.0)

    return pd.DataFrame(
        {
            sample_feature_names[0]: pos_skew,
            sample_feature_names[1]: neg_skew,
            sample_feature_names[2]: normal,
            sample_feature_names[3]: crossing_zero,
            sample_feature_names[4]: zeros,
        }
    )


def test_yeo_johnson_fit_transform_synthetic(
    synthetic_data: pd.DataFrame, sample_feature_names: list[str]
) -> None:
    """Verify Yeo-Johnson transform reduces skewness and standardizes outputs."""
    transformer = YeoJohnsonTransformer(standardize=True, feature_names=sample_feature_names)

    # Check un-fitted transform raises
    with pytest.raises(RuntimeError, match="must be fitted"):
        transformer.transform(synthetic_data)

    transformed_df = transformer.fit_transform(synthetic_data)

    assert isinstance(transformed_df, pd.DataFrame)
    assert transformed_df.shape == synthetic_data.shape
    assert list(transformed_df.columns) == sample_feature_names
    assert not bool(transformed_df.isna().to_numpy().any())

    # Verify skew reduction on the heavily right-skewed feature
    raw_skew = float(synthetic_data[sample_feature_names[0]].skew())
    transformed_skew = float(transformed_df[sample_feature_names[0]].skew())

    assert abs(raw_skew) > 2.0  # Originally heavily skewed
    assert abs(transformed_skew) < abs(raw_skew)  # Skew significantly reduced
    assert abs(transformed_skew) < 1.0  # Near normal

    # Verify standardization properties (mean ~ 0, std ~ 1)
    for col in sample_feature_names:
        assert abs(float(transformed_df[col].mean())) < 1e-2
        assert abs(float(transformed_df[col].std()) - 1.0) < 1e-1


def test_yeo_johnson_rejects_dropped_duplicate(
    synthetic_data: pd.DataFrame, sample_feature_names: list[str]
) -> None:
    """Verify transformer rejects inputs containing the dropped duplicate column (D-1.10)."""
    transformer = YeoJohnsonTransformer(standardize=True, feature_names=sample_feature_names)
    corrupted_data = synthetic_data.copy()
    corrupted_data[DROPPED_DUPLICATE_FEATURE] = 1.0

    with pytest.raises(ValueError, match="Forbidden duplicate column"):
        transformer.fit(corrupted_data)


def test_yeo_johnson_rejects_missing_features(
    synthetic_data: pd.DataFrame, sample_feature_names: list[str]
) -> None:
    """Verify transformer raises on missing expected features."""
    transformer = YeoJohnsonTransformer(standardize=True, feature_names=sample_feature_names)
    incomplete_data = synthetic_data.drop(columns=[sample_feature_names[0]])

    with pytest.raises(ValueError, match="missing 1 canonical features"):
        transformer.fit(incomplete_data)


def test_yeo_johnson_with_real_dataset_skewed_columns() -> None:
    """Verify transformer operates on real skewed EDA features from data/raw/data.csv."""
    csv_path = "data/raw/data.csv"
    try:
        df = pd.read_csv(csv_path, nrows=500)
    except FileNotFoundError:
        pytest.skip("data/raw/data.csv not found (DVC-tracked)")

    # Select canonical features and test full 94-feature transform
    cols_to_select = [c for c in CANONICAL_FEATURES if c in df.columns]
    X = df[cols_to_select]
    assert isinstance(X, pd.DataFrame)
    assert X.shape[1] == 94

    transformer = YeoJohnsonTransformer(standardize=True, feature_names=CANONICAL_FEATURES)
    transformed_X = transformer.fit_transform(X)

    assert transformed_X.shape == (500, 94)
    assert not bool(transformed_X.isna().to_numpy().any())
    assert list(transformed_X.columns) == list(CANONICAL_FEATURES)
