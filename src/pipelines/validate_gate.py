"""Validation Gate Runner — DVC `validate` Stage Entrypoint.

Runs the Great Expectations data contract suite against a specified CSV,
then writes a gate signal file (`outputs/gate_signal.txt`) containing
"PASSED" if and only if every expectation succeeds.

If any expectation fails, this script exits with code 1 and does NOT write
the gate signal file — preventing DVC from marking the `validate` stage as
successful and therefore preventing `stub_train` (or any real downstream
training stage) from running.

Governed by: INV-7 (ADR-007, ADR-013).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.pipelines.data_contracts import validate_dataset


def main() -> None:
    """CLI entrypoint for the DVC validate stage."""
    parser = argparse.ArgumentParser(
        description="ACRAS INV-7 Validation Gate (DVC stage entrypoint)"
    )
    parser.add_argument(
        "dataset",
        nargs="?",
        default="data/raw/data.csv",
        help="Path to the CSV dataset to validate (default: data/raw/data.csv)",
    )
    parser.add_argument(
        "--gate-signal",
        default="outputs/gate_signal.txt",
        help="Path to write the gate signal file on success.",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    gate_path = Path(args.gate_signal)

    print(f"[validate_gate] Running data contract on: {dataset_path}")

    try:
        success, summary = validate_dataset(csv_path=dataset_path)
    except FileNotFoundError as exc:
        print(f"[validate_gate] ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001
        print(f"[validate_gate] UNEXPECTED ERROR during validation: {exc}", file=sys.stderr)
        sys.exit(2)

    print(
        f"[validate_gate] Evaluated: {summary['total_expectations']} expectations | "
        f"Failed: {summary['failed_expectations_count']} | "
        f"Success: {summary['success']}"
    )

    if not success:
        print(
            "[validate_gate] BLOCKED: Data contract failed. "
            "Gate signal file will NOT be written. "
            "Downstream training stage is blocked.",
            file=sys.stderr,
        )
        for item in summary["failed_details"]:
            print(f"  - {item['expectation_type']}: {item['result']}", file=sys.stderr)
        sys.exit(1)

    # Only write the gate signal on full success.
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.write_text("PASSED\n", encoding="utf-8")
    print(f"[validate_gate] PASS: Gate signal written to '{gate_path}'.")
    sys.exit(0)


if __name__ == "__main__":
    main()
