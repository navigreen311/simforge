"""Open re-sits of an exam (ADR-0160): new sittings on the same run_ref, for the battery sweep.

    apps/api/.venv/Scripts/python.exe -m scripts.open_resit --run-ref "<ref>"
    apps/api/.venv/Scripts/python.exe -m scripts.open_resit --run-ref "<ref>" --count 2

Each sitting is a new `OperationRun` row on the ref with its own clock; every earlier sitting is
kept as it is. The hourly `battery_sweep` (:20 UTC) scores each one, oldest first. Prints the
sitting numbers and the times they were opened. The same as `POST /operation/run/resit`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from src.db import SessionLocal
from src.services.operation.sittings import UnknownExam, open_resit, sittings_of


async def main(run_ref: str, count: int) -> int:
    async with SessionLocal() as session:
        try:
            opened = [await open_resit(session, run_ref) for _ in range(count)]
        except UnknownExam as exc:
            print(f"REFUSED: {exc}")
            return 2
        await session.commit()
        print(f"run_ref: {run_ref}")
        for run in await sittings_of(session, run_ref):
            mark = "opened now" if any(o.id == run.id for o in opened) else "kept"
            print(
                f"  sitting {run.sitting}: started {run.startedAt:%Y-%m-%d %H:%M:%S} UTC  "
                f"own={run.sittingVerdict or run.verdict or 'open'}  standing={run.verdict or '-'}"
                f"  ({mark})"
            )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-ref", required=True)
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be at least 1")
    sys.exit(asyncio.run(main(args.run_ref, args.count)))
