"""Operator CLI: why a partition's agents got their verdicts. Codes and counts only.

    apps/api/.venv/Scripts/python.exe -m scripts.partition_outcomes \
        --partition <partition_id>

For each agent's latest sitting: the sitting's result (the weakest seed,
ADR-0121) and, per seed, how the answers arrived, outcomes by module and
class, failure-mode and finding counts. ADR-0114.

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
from src.services.operation.partition_grading import weakest


def _seed_summary(v: HeldOutPartitionVerdict, rows: list[HeldOutPartitionOutcome]) -> dict:
    by_cell: Counter[str] = Counter()
    modes: Counter[str] = Counter()
    findings: Counter[str] = Counter()
    for r in rows:
        by_cell[f"{r.moduleId}/{r.scenarioClass}/{r.outcome}"] += 1
        modes.update(r.failureModes or [])
        findings.update(r.findings or [])
    return {
        "verdict": v.verdict,
        "decided_at": v.decidedAt.isoformat(),
        "protocol": v.protocolVersion,
        "probes": len(rows),
        "answer_states": dict(Counter(r.answerState for r in rows)),
        "by_module_class_outcome": dict(sorted(by_cell.items())),
        "failure_modes": dict(modes.most_common()),
        "findings": dict(findings.most_common()),
    }


async def summarise(session, partition_id: str) -> dict:  # noqa: ANN001
    """Per agent, the latest sitting that has outcomes behind it, seed by seed."""
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
    sittings: dict[str, dict] = {}
    for v in verdicts:
        rows = list(
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
        key = v.sittingId or v.id
        current = sittings.get(v.agentId)
        if current is None or current["sitting"] != key:
            current = {"sitting": key, "seeds": {}}
            sittings[v.agentId] = current
        current["seeds"][str(v.seed)] = _seed_summary(v, rows)
    out: dict = {}
    for agent, sitting in sittings.items():
        per_seed = sitting["seeds"]
        out[agent] = {
            "verdict": weakest([s["verdict"] for s in per_seed.values()]),
            "seeds": per_seed,
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
