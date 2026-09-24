"""Operator CLI: why a partition's agents got their verdicts. Codes and counts only.

    apps/api/.venv/Scripts/python.exe -m scripts.partition_outcomes \
        --partition <partition_id>

For each agent's latest verdict: how the answers arrived, outcomes by
module and class, and failure-mode counts. ADR-0114.

Never prints a probe, an answer or a scenario id. Not a route: no HTTP
path reads a partition's outcomes, and The Office never sees them.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter

from sqlalchemy import select

from src.db import SessionLocal
from src.models.held_out_partition import HeldOutPartitionOutcome, HeldOutPartitionVerdict


async def summarise(session, partition_id: str) -> dict:  # noqa: ANN001
    """Per agent, the latest verdict that has outcomes behind it."""
    verdicts = (
        (
            await session.execute(
                select(HeldOutPartitionVerdict)
                .where(HeldOutPartitionVerdict.partitionId == partition_id)
                .order_by(HeldOutPartitionVerdict.decidedAt)
            )
        )
        .scalars()
        .all()
    )
    out: dict = {}
    for v in verdicts:
        rows = (
            (
                await session.execute(
                    select(HeldOutPartitionOutcome).where(HeldOutPartitionOutcome.verdictId == v.id)
                )
            )
            .scalars()
            .all()
        )
        if not rows:
            continue
        by_cell: Counter[str] = Counter()
        modes: Counter[str] = Counter()
        for r in rows:
            by_cell[f"{r.moduleId}/{r.scenarioClass}/{r.outcome}"] += 1
            modes.update(r.failureModes or [])
        out[v.agentId] = {
            "verdict": v.verdict,
            "decided_at": v.decidedAt.isoformat(),
            "probes": len(rows),
            "answer_states": dict(Counter(r.answerState for r in rows)),
            "by_module_class_outcome": dict(sorted(by_cell.items())),
            "failure_modes": dict(modes.most_common()),
        }
    return out


async def _run(partition_id: str) -> dict:
    async with SessionLocal() as session:
        return await summarise(session, partition_id)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--partition", required=True)
    args = p.parse_args(argv)
    print(json.dumps(asyncio.run(_run(args.partition)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
