"""Operator report for one partition: verdicts, unparseable answers, citation accuracy (ADR-0139).

    apps/api/.venv/Scripts/python.exe -m scripts.partition_report --partition <partition_id>

Codes and counts only - never a scenario, a probe or an answer (ADR-0109).

**Citation accuracy is reported, never gating.** Since ADR-0139 a REFUSE citing any act-rule of
the module is a refusal of the probed rule. Of an agent's REFUSEs on decline probes, this reports
how many named the probed rule exactly, a member of its look-alike group, another act-rule, or
something that is not an act-rule. The go-ahead probes are reported beside it: they are what
stops an agent that refuses everything.

**Slips (ADR-0143).** Per agent: the folded verdict under the partition's rule, any tolerated
slip named in `verdict_detail`, and each slip as a code - seed, module, rule number.

**REFUSE under a reading rule (ADR-0145).** Per agent, how many REFUSEs cited a rule on how to
read a result rather than a prohibited act. Step 1 says such a rule does not forbid the request;
since a quoted refused reading no longer fails, this count is where that habit stays visible.

**Placeholder records (ADR-0151).** Per agent, records whose claim is a template - `<count>`,
`[the number as reported]` - where a value belongs. They pass; the count is where they show.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter, defaultdict
from itertools import groupby

from sqlalchemy import select

from src.db import SessionLocal
from src.models.forge_instruction_set import ForgeInstructionSet
from src.models.held_out_partition import (
    HeldOutPartition,
    HeldOutPartitionOutcome,
    HeldOutPartitionScenario,
    HeldOutPartitionVerdict,
)
from src.services.operation.battery import FINDING_PLACEHOLDER
from src.services.operation.held_out import ObligationKind, obligations_from_never_do
from src.services.operation.held_out_scoring import PERMITTED_CLASS
from src.services.operation.partition_tolerance import (
    RULE_ZERO_TOLERANCE,
    fold_agent,
    is_slip,
)
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION, PARTITION_PROTOCOL_VERSION

#: Citation codes that are a refusal of the probed rule, in order of exactness.
_REFUSALS = ("probed", "same_group", "other_act_rule")


async def report(partition_id: str) -> dict:
    async with SessionLocal() as s:
        partition = await s.get(HeldOutPartition, partition_id)
        rule = partition.verdictRule if partition is not None else None
        # ADR-0145. Which rule numbers are reading rules (not prohibited acts), per module, from
        # the instruction sets the partition was authored against.
        reading_rules: dict[str, set[int]] = {}
        for module, content_hash in (
            (partition.instructionHashes or {}) if partition else {}
        ).items():
            iset = (
                (
                    await s.execute(
                        select(ForgeInstructionSet).where(
                            ForgeInstructionSet.forgeId == partition.forgeId,
                            ForgeInstructionSet.moduleId == module,
                            ForgeInstructionSet.contentHash == content_hash,
                        )
                    )
                )
                .scalars()
                .first()
            )
            if iset is not None:
                reading_rules[module] = {
                    n
                    for n, ob in enumerate(obligations_from_never_do(module, iset.neverDo), start=1)
                    if ob.kind != ObligationKind.PROHIBITED_ACT
                }
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
        # ADR-0143. The probed rule of each slip, as a code: module and 1-based rule number.
        slip_ids = {
            o.scenarioId
            for o in outcomes
            if is_slip(o.outcome, o.scenarioClass, o.failureModes or [])
        }
        refs = (
            {
                sc.id: str(sc.body.get("obligation_ref") or "")
                for sc in (
                    await s.execute(
                        select(HeldOutPartitionScenario).where(
                            HeldOutPartitionScenario.id.in_(slip_ids)
                        )
                    )
                ).scalars()
            }
            if slip_ids
            else {}
        )

    agents: dict[str, dict] = defaultdict(dict)
    for v in sorted(verdicts, key=lambda r: (r.agentId, r.seed if r.seed is not None else -1)):
        agents[v.agentId].setdefault("sittings", []).append(f"{v.seed}:{v.verdict}")
    for agent, rows_v in groupby(
        sorted(verdicts, key=lambda r: r.agentId), key=lambda r: r.agentId
    ):
        folded = fold_agent([(r.verdict, r.slipCount) for r in rows_v], rule)
        agents[agent]["verdict"] = folded.verdict
        agents[agent]["verdict_detail"] = folded.detail
        agents[agent]["tolerated_slips"] = folded.slips if folded.detail else 0
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
        slips = [
            f"seed {o.seed}: {_rule_code(refs.get(o.scenarioId, ''))}"
            for o in rows
            if is_slip(o.outcome, o.scenarioClass, o.failureModes or [])
        ]
        agents[agent].update(
            {
                "answers": len(rows),
                # ADR-0145. Reported, never gating: REFUSEs citing a rule on how to READ a result,
                # which step 1 says does not forbid the request.
                # ADR-0151. Reported, never gating: a template claim where a value belongs.
                "placeholder_records": sum(
                    1 for o in rows if FINDING_PLACEHOLDER in (o.findings or [])
                ),
                "refuse_under_reading_rule": sum(
                    1
                    for o in rows
                    if o.chosenAct == "REFUSE"
                    and o.citedRule in reading_rules.get(o.moduleId, set())
                ),
                "slips": sorted(slips),
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
        "verdict_rule": rule or RULE_ZERO_TOLERANCE,
        "agents": dict(sorted(agents.items())),
    }


def _rule_code(ref: str) -> str:
    """`module#5` (0-based) as `module 6`, the rule number the agent was shown."""
    module, _, index = ref.rpartition("#")
    return f"{module} {int(index) + 1}" if index.isdigit() else ref


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--partition", required=True)
    args = p.parse_args(argv)
    print(json.dumps(asyncio.run(report(args.partition)), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
