"""Stub Training Entrypoint — Phase 0 Gate Proof Only.

This script is a deliberate no-op that exists solely to act as the
downstream stage in the INV-7 gate demonstration (Stage 5 of Phase 0).

It does nothing except read the gate signal file produced by the
validation stage, confirm the gate passed, log the fact, and exit 0.

It will NEVER be reached if the DVC `validate` stage fails, because
`dvc.yaml` makes `stub_train` depend on the gate signal file that the
`validate` stage produces. A failed `validate` stage does not produce
that file, so DVC will refuse to run `stub_train` at all.

This script is NOT production training logic. Real training code belongs
in future Phase 1 work inside this same sub-package.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    """Minimal stub that confirms the gate signal file is present and exits 0."""
    parser = argparse.ArgumentParser(
        description="ACRAS Stub Training Stage (Phase 0 Gate Proof)"
    )
    parser.add_argument(
        "--gate-signal",
        default="outputs/gate_signal.txt",
        help="Path to the gate signal file produced by the validation stage.",
    )
    args = parser.parse_args()

    gate_path = Path(args.gate_signal)
    if not gate_path.is_file():
        print(
            f"[stub_train] BLOCKED: gate signal file not found at '{gate_path}'. "
            "The data contract validation stage must produce this file before training "
            "can proceed. This is the expected behavior for INV-7.",
            file=sys.stderr,
        )
        sys.exit(1)

    content = gate_path.read_text(encoding="utf-8").strip()
    if content != "PASSED":
        print(
            f"[stub_train] BLOCKED: gate signal file contains '{content}', expected 'PASSED'.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        "[stub_train] PASS: Gate signal confirmed. "
        "Stub training stage reached successfully — INV-7 gate is active and working."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
