"""Operator CLI: re-sit a sealed partition at a named seed (ADR-0121).

    apps/api/.venv/Scripts/python.exe -m scripts.resit_partition \\
        --partition <partition_id> --seed <n> [--agent <id> ...]

Puts the partition's probes at seed `n` to each agent (or the named ones),
whatever they last read, as a new sitting. New rows only: nothing written
before is touched. Gate 9.5 then reads the weakest sitting, not the latest.

Not a route, by design (ADR-0050): no request puts a held-out probe. It
holds the partition sweep's own lock, so it never grades beside a
scheduled pass. It prints counts and per-agent verdicts, never a probe.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from src.db import SessionLocal
from src.models.held_out_partition import HeldOutPartition
from src.services.operation import partition_grading
from src.services.village.reader import VillageReaderError
from src.workers.partition_sweep import build_runtime, partition_sweep_lock


class ResitRefused(Exception):
    """The re-sit was not run. Nothing was written."""


async def resit(
    session,  # noqa: ANN001
    lock_session,  # noqa: ANN001
    partition_id: str,
    seed: int,
    *,
    agents: frozenset[str] | None = None,
    runtime=None,  # noqa: ANN001
) -> dict:
    """One operator re-sit. Refuses, writing nothing, on an unsealed partition, a
    held lock or an examiner that cannot sit."""
    partition = await session.get(HeldOutPartition, partition_id)
    if partition is None or partition.status != "sealed":
        raise ResitRefused(f"partition {partition_id!r} is not sealed; only a sealed one is sat.")
    try:
        built = runtime or build_runtime()
    except VillageReaderError as exc:
        raise ResitRefused(f"the Village cannot be read: {exc}") from exc
    examiner = await partition_grading.examiner_runtime(built)
    if isinstance(examiner, str):
        raise ResitRefused(f"the examiner cannot sit: {examiner}")
    async with partition_sweep_lock(lock_session) as acquired:
        if not acquired:
            raise ResitRefused("a partition pass holds the lock; try again when it ends.")
        out = await partition_grading.grade_partition(
            session,
            partition_id,
            runtime=examiner,
            seeds=(seed,),
            only_agents=agents,
            resit=True,
            budget_seconds=partition_grading.PARTITION_AGENT_BUDGET_SECONDS,
        )
    return {
        "partition_id": partition_id,
        "seed": seed,
        "agents": out.agents,
        "put": out.put,
        "recorded": out.recorded,
        "skipped": out.skipped,
    }


async def _run(args: argparse.Namespace) -> dict:
    async with SessionLocal() as session, SessionLocal() as lock_session:
        agents = frozenset(args.agent) if args.agent else None
        return await resit(session, lock_session, args.partition, args.seed, agents=agents)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--partition", required=True)
    p.add_argument("--seed", required=True, type=int)
    p.add_argument("--agent", action="append", help="limit to this agent; may repeat")
    args = p.parse_args(argv)
    try:
        print(json.dumps(asyncio.run(_run(args)), indent=2))
    except ResitRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
