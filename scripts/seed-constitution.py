#!/usr/bin/env python3
"""Seed / ratify Constitution v1.0.0 from docs/CONSTITUTION_v1.0.0.yml (idempotent).

Usage (from repo root, api venv active + DATABASE_URL set):
  python scripts/seed-constitution.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from src.db import SessionLocal, dispose_engine  # noqa: E402
from src.services.governance import ratify_constitution  # noqa: E402

CONSTITUTION_YML = REPO_ROOT / "docs" / "CONSTITUTION_v1.0.0.yml"


async def _main() -> int:
    yaml_content = CONSTITUTION_YML.read_text(encoding="utf-8")
    async with SessionLocal() as session:
        c = await ratify_constitution(session, "v1.0.0", "ivan", yaml_content)
        await session.commit()
        print(f"Constitution ratified: {c.version} (hash {c.contentHash[:12]})")
    await dispose_engine()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
