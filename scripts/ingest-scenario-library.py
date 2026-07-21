#!/usr/bin/env python3
"""Ingest every Pack under packs/ into the registry (idempotent).

Runs the api's ingestion service directly against the configured DATABASE_URL — no
running server required. Re-running is safe (packs are upserted).

Usage (from repo root, with the api venv active and DATABASE_URL set):
  python scripts/ingest-scenario-library.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from src.db import SessionLocal, dispose_engine  # noqa: E402
from src.services.packs.ingestion import ingest_pack  # noqa: E402


async def _main() -> int:
    packs_root = REPO_ROOT / "packs"
    pack_dirs = sorted(d.parent for d in packs_root.rglob("pack.yml"))
    if not pack_dirs:
        print(f"No packs found under {packs_root}")
        return 1

    failures = 0
    async with SessionLocal() as session:
        for pack_dir in pack_dirs:
            result = await ingest_pack(session, str(pack_dir))
            status = "OK" if result.ok else "FAILED"
            print(f"  [{status}] {result.pack_id}  scenarios={result.scenario_count}")
            for issue in result.issues:
                print(f"      [{issue['severity']}] {issue['code']}: {issue['message']}")
            failures += 0 if result.ok else 1

    await dispose_engine()
    print(f"\nIngested {len(pack_dirs) - failures}/{len(pack_dirs)} packs.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
