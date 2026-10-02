"""Operator report for one partition: verdicts, unparseable answers, citation accuracy (ADR-0139).

    apps/api/.venv/Scripts/python.exe -m scripts.partition_report --partition <partition_id>

Codes and counts only - never a scenario, a probe or an answer (ADR-0109).

**Citation accuracy is reported, never gating.** Since ADR-0139 a REFUSE citing any act-rule of
the module is a refusal of the probed rule. Of an agent's REFUSEs on decline probes, this reports
how many named the probed rule exactly, a member of its look-alike group, another act-rule, or
something that is not an act-rule. The go-ahead probes are reported beside it: they are what
stops an agent that refuses everything.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter, defaultdict

from sqlalchemy import select

from src.db import SessionLocal
from src.models.held_out_partition import HeldOutPartitionOutcome, HeldOutPartitionVerdict
from src.services.operation.held_out_scoring import PERMITTED_CLASS
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION, PARTITION_PROTOCOL_VERSION

#: Citation codes that are a refusal of the probed rule, in order of exactness.
_REFUSALS = ("probed", "same_group", "other_act_rule")


async def report(partition_id: str) -> dict:
    async with SessionLocal() as s:
        verdicts = (
            (
                await s.execute(
                    select(HeldOutPartitionVerdict)
                    .where(HeldOutPartitionVerdict.partitionId == partition_id)
                    .where(HeldOutPartitionVerdict.protocolVersion == PARTITION_PROTOCOL_VERSION)
                    .where(HeldOutPartitionVerdict.rubricVersion == OPERATION_RUBRIC_VERSION)
                    .where(HeldOutPartitionVerdict.verdict != "IN_PROGRESS")
                )
            )
            .scalars()
            .all()
        )
        current = {v.id for v in verdicts}
        outcomes = [
            o
            for o in (
                await s.execute(
                    select(HeldOutPartitionOutcome).where(
                        HeldOutPartitionOutcome.partitionId == partition_id
                    )
                )
            )
            .scalars()
            .all()
            if o.verdictId in current
        ]

    agents: dict[str, dict] = defaultdict(dict)
    for v in sorted(verdicts, key=lambda r: (r.agentId, r.seed if r.seed is not None else -1)):
        agents[v.agentId].setdefault("sittings", []).append(f"{v.seed}:{v.verdict}")
    by_agent: dict[str, list[HeldOutPartitionOutcome]] = defaultdict(list)
    for o in outcomes:
        by_agent[o.agentId].append(o)
    for agent, rows in by_agent.items():
        refusals = [
            o.citation
            for o in rows
            if o.scenarioClass == "never_do_violation" and o.chosenAct == "REFUSE"
        ]
        counts = Counter(refusals)
        exact = counts.get("probed", 0)
        go = [o for o in rows if o.scenarioClass == PERMITTED_CLASS]
        agents[agent].update(
            {
                "answers": len(rows),
                "unparseable": sum(1 for o in rows if o.answerState != "answered"),
                "decline_refusals": len(refusals),
                "citations": dict(counts),
                "exact_citation_accuracy": round(exact / len(refusals), 3) if refusals else None,
                "go_ahead": {
                    "put": len(go),
                    "passed": sum(1 for o in go if o.outcome == "PASS"),
                    "failed": sum(1 for o in go if o.outcome == "FAIL"),
                },
            }
        )
    return {
        "partition_id": partition_id,
        "protocol": PARTITION_PROTOCOL_VERSION,
        "rubric": OPERATION_RUBRIC_VERSION,
        "agents": dict(sorted(agents.items())),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--partition", required=True)
    args = p.parse_args(argv)
    print(json.dumps(asyncio.run(report(args.partition)), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
