"""Unit tests for the Great Expectations data contract module."""

import hashlib
from pathlib import Path

import great_expectations as gx
import pytest

from src.pipelines.data_contracts import (
    SUITE_NAME,
    build_bankruptcy_suite,
    validate_dataset,
)

TRACKED_SUITE_PATH = Path("gx/expectations/bankruptcy_data_suite.json")


def _sha256(path: Path) -> str:
    """Return the hex SHA-256 digest of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_build_bankruptcy_suite() -> None:
    """Verify that build_bankruptcy_suite builds a suite with expected name and counts."""
    suite = build_bankruptcy_suite()
    assert suite.name == SUITE_NAME
    assert len(suite.expectations) == 46


def test_build_bankruptcy_suite_does_not_mutate_tracked_suite() -> None:
    """Building the default suite must not rewrite the tracked expectation JSON.

    Regression for the suite-mutation defect: the default (no-context) build was
    loading the file context and persisting fresh expectation UUIDs, so a plain
    ``pytest`` run dirtied ``gx/expectations/bankruptcy_data_suite.json``.
    """
    before = _sha256(TRACKED_SUITE_PATH)
    suite = build_bankruptcy_suite()
    assert suite.name == SUITE_NAME
    assert len(suite.expectations) == 46
    assert _sha256(TRACKED_SUITE_PATH) == before, (
        "build_bankruptcy_suite() mutated the tracked suite file; "
        "the default build must be ephemeral."
    )


def test_build_bankruptcy_suite_save_is_opt_in() -> None:
    """Persistence is opt-in: only ``save=True`` registers into the context.

    This proves the invariance test above is sensitive — a revert to default-save
    would re-trip it, because the default call would register the suite.
    """
    context = gx.get_context(mode="ephemeral")

    build_bankruptcy_suite(context=context)
    try:
        context.suites.get(SUITE_NAME)
    except Exception:
        not_persisted = True
    else:
        not_persisted = False
    assert not_persisted, "default build must not persist into the context"

    build_bankruptcy_suite(context=context, save=True)
    loaded = context.suites.get(SUITE_NAME)
    assert loaded.name == SUITE_NAME


def test_validate_dataset_raw_data() -> None:
    """Verify that the verified raw bankruptcy dataset passes the data contract 100%."""
    data_path = Path("data/raw/data.csv")
    if not data_path.exists():
        pytest.skip("Raw dataset not present (DVC-tracked) — skipping full raw data test.")

    success, summary = validate_dataset(data_path)
    assert success is True
    assert summary["success"] is True
    assert summary["failed_expectations_count"] == 0
    assert summary["total_expectations"] == 46


def test_validate_dataset_file_not_found() -> None:
    """Verify that validate_dataset raises FileNotFoundError for missing paths."""
    with pytest.raises(FileNotFoundError):
        validate_dataset("nonexistent_path/bad_file.csv")
