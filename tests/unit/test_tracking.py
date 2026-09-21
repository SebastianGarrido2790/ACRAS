"""Unit tests for MLflow tracking module.

Verifies that local file-based tracking initializes properly and logs runs,
parameters, metrics, and tags correctly without polluting the main repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from mlflow.client import MlflowClient

from src.pipelines.tracking import (
    compute_file_sha256,
    init_tracking,
    log_data_contract_run,
)


def test_compute_file_sha256(tmp_path: Path) -> None:
    """Verify SHA-256 calculation on a known sample file."""
    sample_file = tmp_path / "sample.txt"
    sample_file.write_text("acras_test_data", encoding="utf-8")

    expected_hash = "CCCD30299E2D52AFE648FFFFEE3D55EE0EAD614ED8917FBD874CC38C236F7627"
    computed = compute_file_sha256(sample_file)
    assert computed == expected_hash


def test_init_tracking(tmp_path: Path) -> None:
    """Verify that init_tracking sets up a new local tracking store."""
    tracking_dir = tmp_path / "mlruns"
    exp_id = init_tracking(experiment_name="test-exp", tracking_uri=tracking_dir)

    assert exp_id is not None
    client = MlflowClient(tracking_uri=tracking_dir.resolve().as_uri())
    exp = client.get_experiment(exp_id)
    assert exp is not None
    assert exp.name == "test-exp"


def test_log_data_contract_run_real_data(tmp_path: Path) -> None:
    """Verify logging a complete data contract run with real raw dataset."""
    data_path = Path("data/raw/data.csv")
    if not data_path.exists():
        pytest.skip("Raw data not present for tracking test.")

    tracking_dir = tmp_path / "mlruns"
    run = log_data_contract_run(
        dataset_path=data_path,
        tracking_uri=tracking_dir,
        experiment_name="test-contract-exp",
    )

    client = MlflowClient(tracking_uri=tracking_dir.resolve().as_uri())
    queried_run = client.get_run(run.info.run_id)

    assert queried_run.info.status == "FINISHED"

    # Verify Parameters
    params = queried_run.data.params
    assert params["gx_suite_name"] == "bankruptcy_data_suite"
    assert params["contract_passed"] == "True"
    assert "dataset_sha256" in params
    assert len(params["dataset_sha256"]) == 64

    # Verify Metrics
    metrics = queried_run.data.metrics
    assert metrics["total_rows"] == 6819.0
    assert metrics["total_columns"] == 96.0
    assert metrics["expectations_evaluated"] == 46.0
    assert metrics["expectations_failed"] == 0.0
    assert metrics["contract_success_flag"] == 1.0

    # Verify Tags
    tags = queried_run.data.tags
    assert tags["phase"] == "0"
    assert tags["stage"] == "7"
    assert tags["governed_by"] == "INV-7"
