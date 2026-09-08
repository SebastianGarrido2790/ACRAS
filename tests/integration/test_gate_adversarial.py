"""Adversarial Gate Integration Tests — Stage 5 of Phase 0.

Three checks required by Gate 5:

  (a) VALID PATH — the real dataset passes the data contract gate; the stub
      training stage is reachable (its entry-point runs and exits 0).

  (b) BLOCKED PATH — the corrupted fixture fails the data contract gate; the
      gate signal file is NOT written; the stub training stage is unreachable.

  (c) FALSIFICATION — the gate is temporarily disabled (monkeypatched to always
      return PASS); the corrupted fixture no longer blocks the training stage.
      This confirms that test (b) is sensitive to whether the gate is active —
      it cannot pass vacuously.

Governed by: INV-7 (ADR-007, ADR-013).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures / constants
# ---------------------------------------------------------------------------

REAL_DATA = Path("data/raw/data.csv")
CORRUPTED_DATA = Path("tests/fixtures/corrupted_data.csv")
STUB_TRAIN_MODULE = "src.pipelines.training.stub_train"


def _run_validate_gate(
    dataset: Path,
    gate_signal: Path,
) -> subprocess.CompletedProcess[str]:
    """Run the validate_gate module as a subprocess, returning its result."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "src.pipelines.validate_gate",
            str(dataset),
            "--gate-signal",
            str(gate_signal),
        ],
        capture_output=True,
        text=True,
    )


def _run_stub_train(gate_signal: Path) -> subprocess.CompletedProcess[str]:
    """Run the stub_train module as a subprocess, returning its result."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            STUB_TRAIN_MODULE,
            "--gate-signal",
            str(gate_signal),
        ],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# (a) Valid path: gate passes → stub training stage is reachable
# ---------------------------------------------------------------------------


def test_valid_data_passes_gate_and_reaches_stub_train(
    tmp_path: Path,
) -> None:
    """[GATE 5a] Valid dataset: contract passes → gate signal written → stub train runs.

    This is the green path. The real dataset must satisfy all 46 expectations,
    the gate signal file must be written, and the stub training stage must run
    successfully (exit code 0) when provided that signal.
    """
    if not REAL_DATA.exists():
        pytest.skip("Real dataset not present — skipping green-path test.")

    gate_signal = tmp_path / "gate_signal.txt"

    # --- Step 1: validate gate ---
    result_validate = _run_validate_gate(REAL_DATA, gate_signal)
    assert result_validate.returncode == 0, (
        f"[validate_gate] unexpected failure on valid data.\n"
        f"stdout: {result_validate.stdout}\n"
        f"stderr: {result_validate.stderr}"
    )
    assert gate_signal.exists(), (
        "Gate signal file was NOT written even though validation passed."
    )
    assert gate_signal.read_text(encoding="utf-8").strip() == "PASSED"

    # --- Step 2: stub train ---
    result_train = _run_stub_train(gate_signal)
    assert result_train.returncode == 0, (
        f"[stub_train] should have succeeded but exited {result_train.returncode}.\n"
        f"stdout: {result_train.stdout}\n"
        f"stderr: {result_train.stderr}"
    )
    assert "PASS" in result_train.stdout


# ---------------------------------------------------------------------------
# (b) Blocked path: gate fails → gate signal absent → stub training unreachable
# ---------------------------------------------------------------------------


def test_corrupted_data_blocked_by_gate(tmp_path: Path) -> None:
    """[GATE 5b] Corrupted fixture: contract fails → gate signal NOT written → stub blocked.

    The corrupted fixture has three deliberate violations:
      - Null in Bankrupt? (ExpectColumnValuesToNotBeNull)
      - ROA(A)=999 out of [0,1] range (ExpectColumnValuesToBeBetween)
      - Net Income Flag=0 not in value_set=[1] (ExpectColumnValuesToBeInSet)

    The gate must catch at least one of these and exit non-zero without writing
    the gate signal file.  The stub training stage must then also fail because
    the signal file is absent.
    """
    assert CORRUPTED_DATA.exists(), (
        f"Corrupted fixture not found at '{CORRUPTED_DATA}'. "
        "Run 'make fixtures' or check tests/fixtures/."
    )

    gate_signal = tmp_path / "gate_signal.txt"

    # --- Step 1: validate gate must fail ---
    result_validate = _run_validate_gate(CORRUPTED_DATA, gate_signal)
    assert result_validate.returncode != 0, (
        "[validate_gate] should have FAILED on corrupted data but returned 0 (gate is broken).\n"
        f"stdout: {result_validate.stdout}\n"
        f"stderr: {result_validate.stderr}"
    )
    assert not gate_signal.exists(), (
        "Gate signal file was written even though validation FAILED (gate is broken)."
    )

    # --- Step 2: stub train must also fail — gate signal is absent ---
    result_train = _run_stub_train(gate_signal)
    assert result_train.returncode != 0, (
        f"[stub_train] should have been BLOCKED (no gate signal) but exited 0.\n"
        f"stdout: {result_train.stdout}\n"
        f"stderr: {result_train.stderr}"
    )
    assert "BLOCKED" in result_train.stderr


# ---------------------------------------------------------------------------
# (c) Falsification: disable the gate → corrupted data is no longer blocked
#     This rules out the test being vacuously true regardless of gate state.
# ---------------------------------------------------------------------------


def test_falsification_disabled_gate_lets_corrupted_data_through(
    tmp_path: Path,
) -> None:
    """[GATE 5c] FALSIFICATION — disabled gate no longer blocks corrupted data.

    We monkeypatch validate_dataset to always return (True, {...}) regardless of
    the actual data.  We then run the gate runner logic directly (in-process, not
    subprocess) to confirm that the gate signal file WOULD be written, and that
    stub_train would succeed.

    This establishes that test (b) is testing gate presence, not some other
    property of the data — the test CAN fail, and removing the gate is what makes
    it fail.
    """
    assert CORRUPTED_DATA.exists(), (
        f"Corrupted fixture not found at '{CORRUPTED_DATA}'."
    )

    gate_signal = tmp_path / "gate_signal.txt"

    # Patch validate_dataset to simulate the gate being disabled / bypassed.
    fake_summary = {
        "dataset_path": str(CORRUPTED_DATA),
        "total_rows": 3,
        "total_columns": 96,
        "total_expectations": 46,
        "failed_expectations_count": 0,
        "success": True,
        "failed_details": [],
    }

    with patch(
        "src.pipelines.validate_gate.validate_dataset",
        return_value=(True, fake_summary),
    ):
        # Import and call main() with sys.argv patched to target our paths.
        import importlib
        import sys as _sys

        validate_gate_mod = importlib.import_module("src.pipelines.validate_gate")

        _sys.argv = [
            "validate_gate",
            str(CORRUPTED_DATA),
            "--gate-signal",
            str(gate_signal),
        ]

        # main() calls sys.exit(0) on success — catch SystemExit.
        with pytest.raises(SystemExit) as exc_info:
            validate_gate_mod.main()

        assert exc_info.value.code == 0, (
            f"Expected exit 0 with gate disabled, got {exc_info.value.code}."
        )

    # Gate signal must now exist (gate was bypassed).
    assert gate_signal.exists(), (
        "Gate signal was NOT written even with the gate disabled — something else is broken."
    )
    assert gate_signal.read_text(encoding="utf-8").strip() == "PASSED"

    # Stub train must succeed.
    result_train = _run_stub_train(gate_signal)
    assert result_train.returncode == 0, (
        f"[stub_train] should succeed with gate disabled, but got exit {result_train.returncode}.\n"
        f"stdout: {result_train.stdout}\n"
        f"stderr: {result_train.stderr}"
    )
    assert "PASS" in result_train.stdout
