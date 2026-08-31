#!/usr/bin/env python3
"""Module size checker — ACRAS CI enforcement script.

Walks ``src/`` and fails with a non-zero exit code if any tracked ``.py`` file
is at or above the 1,000-line ceiling defined in the project harness (§7).

Usage::

    uv run python scripts/check_module_size.py

Exit codes:
    0 — All tracked files are under the ceiling.
    1 — One or more files are at or above the ceiling (names are printed).
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Maximum number of source lines allowed per module.
MAX_LINES: int = 1000

#: Directories to scan (relative to repo root).
SCAN_ROOTS: list[str] = ["src"]

#: File extensions to check.
EXTENSIONS: tuple[str, ...] = (".py",)


def count_lines(path: Path) -> int:
    """Return the number of lines in *path* (newline-terminated or not)."""
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError as exc:
        print(f"  WARNING: could not read {path}: {exc}", file=sys.stderr)
        return 0


def main() -> int:  # noqa: D401
    """Run the size check; return 0 if all clear, 1 if any file exceeds the limit."""
    repo_root = Path(__file__).resolve().parent.parent
    violators: list[tuple[Path, int]] = []

    for root_name in SCAN_ROOTS:
        scan_root = repo_root / root_name
        if not scan_root.is_dir():
            print(f"  WARNING: scan root '{scan_root}' does not exist — skipping.",
                  file=sys.stderr)
            continue

        for path in sorted(scan_root.rglob("*")):
            if path.suffix not in EXTENSIONS:
                continue
            if any(part.startswith("__pycache__") for part in path.parts):
                continue
            n = count_lines(path)
            if n >= MAX_LINES:
                violators.append((path.relative_to(repo_root), n))

    if violators:
        print(f"[check_module_size] FAIL — {len(violators)} file(s) at or above "
              f"{MAX_LINES}-line ceiling:")
        for rel_path, n_lines in violators:
            print(f"  {rel_path}  ({n_lines} lines)")
        return 1

    print(f"[check_module_size] PASS — all files under {MAX_LINES} lines.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
