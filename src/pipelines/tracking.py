"""MLflow Tracking Module for ACRAS Pipelines.

Provides standardized experiment management, parameter logging, and metric recording
for data contract validation and downstream model training pipelines.

Governed by:
    D-0.4: Local file-based tracking store (`./mlruns`, gitignored).
    INV-7: Training and validation pipelines must produce verifiable, tracked metrics.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import mlflow
from mlflow.entities import Run

from src.pipelines.data_contracts import SUITE_NAME, validate_dataset

DEFAULT_EXPERIMENT_NAME: str = "acras-data-pipeline"
DEFAULT_TRACKING_DIR: str = "./mlruns"


def compute_file_sha256(path: Path | str) -> str:
    """Compute SHA-256 hash of a file.

    Args:
        path: Path to the target file.

    Returns:
        Hexadecimal SHA-256 digest in uppercase.
    """
    file_path = Path(path)
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest().upper()


def init_tracking(
    experiment_name: str = DEFAULT_EXPERIMENT_NAME,
    tracking_uri: str | Path | None = None,
) -> str:
    """Initialize MLflow tracking URI and experiment.

    Args:
        experiment_name: Name of the MLflow experiment.
        tracking_uri: Optional URI/path for the tracking store (defaults to ./mlruns).

    Returns:
        Experiment ID.
    """
    if tracking_uri is None:
        target_path = Path(DEFAULT_TRACKING_DIR).resolve()
        resolved_uri = target_path.as_uri()
    elif isinstance(tracking_uri, Path):
        resolved_uri = tracking_uri.resolve().as_uri()
    elif tracking_uri.startswith(("http://", "https://", "file://", "sqlite:", "postgresql:")):
        resolved_uri = tracking_uri
    else:
        resolved_uri = Path(tracking_uri).resolve().as_uri()

    mlflow.set_tracking_uri(resolved_uri)
    experiment = mlflow.set_experiment(experiment_name)
    assert experiment.experiment_id is not None
    return experiment.experiment_id


def log_data_contract_run(
    dataset_path: Path | str = "data/raw/data.csv",
    tracking_uri: str | Path | None = None,
    experiment_name: str = DEFAULT_EXPERIMENT_NAME,
) -> Run:
    """Run data contract validation and log parameters and metrics to MLflow.

    Args:
        dataset_path: Path to the raw dataset CSV file.
        tracking_uri: Optional custom tracking store path.
        experiment_name: Name of the target MLflow experiment.

    Returns:
        Active MLflow Run object.
    """
    path = Path(dataset_path)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset file not found at: {path}")

    init_tracking(experiment_name=experiment_name, tracking_uri=tracking_uri)

    # Compute cryptographic checksum
    sha256_hash = compute_file_sha256(path)

    # Execute data contract validation
    success, summary = validate_dataset(csv_path=path)

    # Log to MLflow
    with mlflow.start_run(run_name="phase-0-data-contract-verification") as run:
        # Tags
        mlflow.set_tags(
            {
                "phase": "0",
                "stage": "7",
                "governed_by": "INV-7",
                "component": "data_contracts",
            }
        )

        # Parameters
        mlflow.log_params(
            {
                "dataset_path": str(path.as_posix()),
                "dataset_sha256": sha256_hash,
                "gx_suite_name": SUITE_NAME,
                "contract_passed": str(success),
            }
        )

        # Metrics
        mlflow.log_metrics(
            {
                "total_rows": float(summary["total_rows"]),
                "total_columns": float(summary["total_columns"]),
                "expectations_evaluated": float(summary["total_expectations"]),
                "expectations_failed": float(summary["failed_expectations_count"]),
                "contract_success_flag": 1.0 if success else 0.0,
            }
        )

        return run


def main() -> None:
    """CLI entrypoint for logging a data contract validation run to MLflow."""
    parser = argparse.ArgumentParser(
        description="ACRAS MLflow Tracking — Log Data Contract Validation Run"
    )
    parser.add_argument(
        "dataset",
        nargs="?",
        default="data/raw/data.csv",
        help="Path to the dataset CSV file (default: data/raw/data.csv)",
    )
    parser.add_argument(
        "--tracking-uri",
        default=DEFAULT_TRACKING_DIR,
        help="Path or URI for MLflow tracking store (default: ./mlruns)",
    )
    parser.add_argument(
        "--experiment-name",
        default=DEFAULT_EXPERIMENT_NAME,
        help=f"Target MLflow experiment name (default: {DEFAULT_EXPERIMENT_NAME})",
    )
    args = parser.parse_args()

    print(f"[tracking] Initializing tracking at: {args.tracking_uri}")
    print(f"[tracking] Target experiment: {args.experiment_name}")
    print(f"[tracking] Validating and logging: {args.dataset}")

    try:
        run = log_data_contract_run(
            dataset_path=args.dataset,
            tracking_uri=args.tracking_uri,
            experiment_name=args.experiment_name,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[tracking] ERROR during MLflow run logging: {exc}", file=sys.stderr)
        sys.exit(1)

    print("[tracking] PASS: Successfully logged MLflow run!")
    print(f"  - Run ID: {run.info.run_id}")
    print(f"  - Experiment ID: {run.info.experiment_id}")
    print(f"  - Artifact URI: {run.info.artifact_uri}")
    sys.exit(0)


if __name__ == "__main__":
    main()
