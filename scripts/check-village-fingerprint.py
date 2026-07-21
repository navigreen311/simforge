#!/usr/bin/env python3
"""Print the current Village schema fingerprint and drift vs the expected value.

Self-contained (no api venv needed) — mirrors
`apps/api/src/services/village/reader.py::structural_paths`. Keep the two in sync;
a contract test asserts parity in a later phase.

Usage:
  python scripts/check-village-fingerprint.py [VILLAGE_DATA_PATH]
Env:
  VILLAGE_DATA_PATH               (fallback if arg omitted)
  VILLAGE_OS_VERSION_FINGERPRINT  (expected value; drift is reported vs this)
Exit code: 0 = no drift, 3 = drift detected, 2 = village path missing.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

_FINGERPRINT_SUBDIRS = ("knowledge", "emotional_ledger", "memory", "tasks")


def structural_paths(village_data_path: Path) -> list[str]:
    paths: list[str] = []
    agents_dir = village_data_path / "agents"
    if not agents_dir.exists():
        return paths
    for agent_dir in sorted(agents_dir.iterdir()):
        if not agent_dir.is_dir():
            continue
        paths.append(agent_dir.name)
        for subdir in _FINGERPRINT_SUBDIRS:
            if (agent_dir / subdir).exists():
                paths.append(f"{agent_dir.name}/{subdir}")
    return sorted(paths)


def fingerprint(village_data_path: Path) -> str:
    hasher = hashlib.sha256()
    hasher.update("\n".join(structural_paths(village_data_path)).encode())
    return hasher.hexdigest()


def main() -> int:
    raw = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
        "VILLAGE_DATA_PATH", "./village-data-local/VillageData"
    )
    path = Path(raw)
    if not path.is_dir():
        print(f"ERROR: Village data path not found: {path}", file=sys.stderr)
        return 2

    current = fingerprint(path)
    expected = os.environ.get("VILLAGE_OS_VERSION_FINGERPRINT", "")
    print(f"current : {current}")
    print(f"expected: {expected or '(unset)'}")

    if expected and expected not in ("dev-fingerprint",) and current != expected:
        print("DRIFT DETECTED", file=sys.stderr)
        return 3
    print("no drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
