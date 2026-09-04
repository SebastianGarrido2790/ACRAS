"""Unit tests for the Great Expectations data contract module."""

from pathlib import Path

import pytest

from src.pipelines.data_contracts import (
    SUITE_NAME,
    build_bankruptcy_suite,
    validate_dataset,
)


def test_build_bankruptcy_suite() -> None:
    """Verify that build_bankruptcy_suite builds a suite with expected name and counts."""
    suite = build_bankruptcy_suite()
    assert suite.name == SUITE_NAME
    assert len(suite.expectations) == 46


def test_validate_dataset_raw_data() -> None:
    """Verify that the verified raw bankruptcy dataset passes the data contract 100%."""
    data_path = Path("data/raw/data.csv")
    assert data_path.exists(), "Raw dataset must exist for data contract unit test"

    success, summary = validate_dataset(data_path)
    assert success is True
    assert summary["success"] is True
    assert summary["failed_expectations_count"] == 0
    assert summary["total_expectations"] == 46


def test_validate_dataset_file_not_found() -> None:
    """Verify that validate_dataset raises FileNotFoundError for missing paths."""
    with pytest.raises(FileNotFoundError):
        validate_dataset("nonexistent_path/bad_file.csv")
