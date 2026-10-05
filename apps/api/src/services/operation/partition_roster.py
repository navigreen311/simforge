"""Who sits a partition: the one roster the grader and the verdict both read (ADR-0152).

WHAT IT IS
==========

    The venture's agents on the partition's forge, read off Unit-A runs, who
    operate at least one module the partition covers. Each agent carries only
    those modules.

    The venture reaches SimForge only as segment 2 of the run ref (ADR-0058),
    so that is what is matched. The partition's module scope is the key set of
    its `instructionHashes`, recorded at authoring (ADR-0125, ADR-0129).

WHY ONE FUNCTION
================

    ADR-0110 rostered every agent with any run and wrote NOT_RUN for one with
    no module in scope. Verdict rows are append-only, so a grader that stops
    writing that row is not enough: the verdict would still read the old one.
    Both sides ask this function, so they cannot disagree about who sits.

WHAT IT IS NOT
==============

    Not a grant check. SimForge holds no grants; The Office does. An agent
    whose grant was retired but whose runs touched a partition module is still
    rostered. The grant-backed roster is on the backlog.

WHO MAY IMPORT THIS
===================

    The grader and the verdict service. It reads `OperationRun` and the
    partition's own row, never a scenario, so the request path may reach it.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.operation_run import OperationRun

#: The run-ref prefix The Office mints (`mint_run_ref`), venture in segment 2:
#: `office:{venture_id}:{forge_id}:{target}:...`. Measured, ADR-0110.
OFFICE_REF_PREFIX = "office"


def venture_of_run_ref(run_ref: str) -> str | None:
    """The venture segment of an Office-minted run ref, or None.

    The only place the operation path carries the venture (ADR-0058). A ref
    not minted by The Office names no venture and selects no agent.
    """
    parts = (run_ref or "").split(":")
    if len(parts) < 3 or parts[0] != OFFICE_REF_PREFIX or not parts[1]:
        return None
    return parts[1]


@dataclass(frozen=True, slots=True)
class PartitionAgent:
    """One agent of a venture on a forge, and the modules it operates there.

    `agent_id` is the Village ref - the id the examiner resolves and the one
    a probe is put to (ADR-0083: `villageAgentRef`, else `agentId`).
    """

    agent_id: str
    modules: tuple[str, ...]


async def partition_roster(
    session: AsyncSession,
    *,
    venture_id: str,
    forge_id: str,
    scope: Collection[str] | None,
) -> list[PartitionAgent]:
    """The agents who sit the partition, sorted by agent id.

    `scope` is the partition's module set. An agent with no module in it is
    not on the roster: the partition has nothing to put to it (ADR-0152).
    `None` - a partition authored before ADR-0125 recorded its modules - keeps
    the ADR-0110 roster, every agent with a run; such a partition is never
    graded, and its verdict reads as it always did.
    """
    rows = (
        await session.execute(
            select(
                OperationRun.runRef,
                OperationRun.moduleId,
                OperationRun.agentId,
                OperationRun.villageAgentRef,
            ).where(
                OperationRun.forgeId == forge_id,
                OperationRun.unit == "A",
                OperationRun.moduleId.is_not(None),
                OperationRun.agentId.is_not(None),
            )
        )
    ).all()
    modules: dict[str, set[str]] = {}
    for run_ref, module_id, agent_id, village_ref in rows:
        if venture_of_run_ref(run_ref) != venture_id:
            continue
        if scope is not None and module_id not in scope:
            continue
        who = village_ref or agent_id
        modules.setdefault(who, set()).add(module_id)
    return [PartitionAgent(a, tuple(sorted(m))) for a, m in sorted(modules.items())]


__all__ = [
    "OFFICE_REF_PREFIX",
    "PartitionAgent",
    "partition_roster",
    "venture_of_run_ref",
]
