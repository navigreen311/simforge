"""Write the results page for a sandbox run (ADR-0166 stage 6).

    cd apps/api && python -m scripts.sandbox_run_page --run <runRef> --out <dir>
    cd apps/api && python -m scripts.sandbox_run_page --demo --out <dir>

`--run` reads one `SandboxRun` and its steps from the database (`DATABASE_URL`), selects only,
and writes `sandbox-run-<runRef>.html`.

`--demo` records the fake run (`src.services.sandbox.demo`) through the real record into an
in-memory SQLite database holding only the two sandbox tables, and writes
`sandbox-run-demo.html`. It reads and writes no other database. Needs `aiosqlite` (a dev
dependency).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.models.sandbox_run import SandboxRun, SandboxStep
from src.services.sandbox.demo import FAKE_NOTE, record_demo_run
from src.services.sandbox.page import load_run, render_run_page
from src.services.sandbox.record import SandboxRefused


async def demo_page() -> str:
    """The fake run, recorded in memory, as its page."""
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(
                SandboxRun.metadata.create_all,
                tables=[
                    SandboxRun.metadata.tables[t.__tablename__] for t in (SandboxRun, SandboxStep)
                ],
            )
        maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        async with maker() as db:
            run = await record_demo_run(db)
            run, steps = await load_run(db, run.runRef)
            return render_run_page(run, steps, fake_note=FAKE_NOTE)
    finally:
        await engine.dispose()


async def run_page(run_ref: str) -> str:
    from src.db import SessionLocal

    async with SessionLocal() as db:
        run, steps = await load_run(db, run_ref)
        return render_run_page(run, steps)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--run", help="the run's runRef")
    which.add_argument("--demo", action="store_true", help="record the fake run in memory")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        html = asyncio.run(demo_page() if args.demo else run_page(args.run))
    except SandboxRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / ("sandbox-run-demo.html" if args.demo else f"sandbox-run-{args.run}.html")
    path.write_bytes(html.encode("utf-8"))
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
