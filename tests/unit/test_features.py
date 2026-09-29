"""Unit tests for the canonical feature schema module."""

import pandas as pd
import pytest

from src.schemas.features import (
    CANONICAL_FEATURES,
    DROPPED_DUPLICATE_FEATURE,
    RETAINED_DUPLICATE_FEATURE,
    TARGET_COLUMN,
)


def test_canonical_features_count_and_types() -> None:
    """Verify that canonical features contains exactly 94 strings."""
    assert len(CANONICAL_FEATURES) == 94
    assert len(set(CANONICAL_FEATURES)) == 94  # All unique
    for feat in CANONICAL_FEATURES:
        assert isinstance(feat, str)
        assert len(feat.strip()) > 0


def test_dropped_and_retained_duplicates() -> None:
    """Verify D-1.10 / ADR-024 duplicate column resolution."""
    assert DROPPED_DUPLICATE_FEATURE not in CANONICAL_FEATURES
    assert RETAINED_DUPLICATE_FEATURE in CANONICAL_FEATURES
    assert TARGET_COLUMN not in CANONICAL_FEATURES


def test_canonical_features_match_raw_dataset() -> None:
    """Verify canonical features against the live DVC-tracked dataset."""
    csv_path = "data/raw/data.csv"
    try:
        df = pd.read_csv(csv_path, nrows=5)
    except FileNotFoundError:
        pytest.skip("data/raw/data.csv not found (DVC-tracked)")

    assert TARGET_COLUMN in df.columns
    assert DROPPED_DUPLICATE_FEATURE in df.columns
    assert RETAINED_DUPLICATE_FEATURE in df.columns

    # Verify that all 94 canonical features exist in raw data
    raw_cols = set(df.columns)
    for col in CANONICAL_FEATURES:
        assert col in raw_cols

    # Verify total columns: 94 canonical + 1 dropped + 1 target = 96
    expected_cols = set(CANONICAL_FEATURES) | {DROPPED_DUPLICATE_FEATURE, TARGET_COLUMN}
    assert raw_cols == expected_cols
