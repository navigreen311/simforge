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

    Not a grant check of its own. SimForge holds no grants; The Office does.
    Without a recorded roster, an agent whose grant was retired but whose runs
    touched a partition module is still rostered.

THE RECORDED ROSTER (ADR-0162)
==============================

    A partition authored with The Office's roster statement - its live grants
    on the partition's modules - is sat by exactly those grants' agents. No
    run is read, so an agent whose grant was retired is not rostered, however
    many runs it has. The roster is recorded at authoring and folded into the
    partition's `contentDigest` at seal.

    A partition with no recorded roster keeps the ADR-0152 roster.

WHO MAY IMPORT THIS
===================

    The grader and the verdict service. It reads `OperationRun` and the
    partition's own row, never a scenario, so the request path may reach it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError
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


# --- the recorded roster (ADR-0162) -----------------------------------------


class RosterRefused(ValueError):
    """A roster statement SimForge will not record. `code` names the rule."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


#: The statement is not the contract's shape.
REFUSED_ROSTER_INVALID = "roster_statement_invalid"
#: It names a venture or forge other than the partition's.
REFUSED_ROSTER_ELSEWHERE = "roster_names_another_venture_or_forge"
#: Two grants share an id.
REFUSED_ROSTER_REPEATS = "roster_repeats_a_grant"
#: No grant is on a module the partition covers: it would be sat by nobody.
REFUSED_ROSTER_EMPTY = "roster_sits_nobody"


class _Grant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grant_id: str = Field(min_length=1)
    #: The Village agent ref: the id a probe is put to (ADR-0083).
    agent_id: str = Field(min_length=1)
    module_id: str = Field(min_length=1)


class RosterStatement(BaseModel):
    """What The Office states at authoring: its live grants for one venture and forge."""

    model_config = ConfigDict(extra="forbid")

    venture_id: str = Field(min_length=1)
    forge_id: str = Field(min_length=1)
    #: When The Office read its grants. Recorded, not compared.
    stated_at: datetime
    grants: list[_Grant]


def record_roster(
    statement: Mapping, *, venture_id: str, forge_id: str, scope: Collection[str]
) -> dict:
    """The roster to record on a partition, from The Office's statement, or a refusal.

    Only grants on a module in `scope` are kept: a grant on a module the partition does not
    cover has nothing to sit (ADR-0152). Sorted, so one set of grants records one way.
    """
    try:
        parsed = RosterStatement.model_validate(statement)
    except ValidationError as exc:
        rules = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'statement'}: {e['msg']}"
            for e in exc.errors(include_url=False, include_context=False)
        )
        raise RosterRefused(
            f"the roster statement is invalid: {rules}", REFUSED_ROSTER_INVALID
        ) from exc
    if parsed.venture_id.strip() != venture_id or parsed.forge_id.strip() != forge_id:
        raise RosterRefused(
            f"the roster states {parsed.venture_id!r} x {parsed.forge_id!r}; the partition "
            f"is {venture_id!r} x {forge_id!r}.",
            REFUSED_ROSTER_ELSEWHERE,
        )
    ids = [g.grant_id.strip() for g in parsed.grants]
    if len(set(ids)) != len(ids):
        raise RosterRefused("the roster names one grant twice.", REFUSED_ROSTER_REPEATS)
    grants = sorted(
        (
            {
                "grant_id": g.grant_id.strip(),
                "agent_id": g.agent_id.strip(),
                "module_id": g.module_id.strip(),
            }
            for g in parsed.grants
            if g.module_id.strip() in scope
        ),
        key=lambda g: (g["agent_id"], g["module_id"], g["grant_id"]),
    )
    if not grants:
        raise RosterRefused(
            "no grant in the roster is on a module the partition covers; it would be sat "
            "by nobody.",
            REFUSED_ROSTER_EMPTY,
        )
    return {"stated_at": parsed.stated_at.isoformat(), "grants": grants}


def roster_digest(roster: Mapping) -> str:
    """sha256 of the canonical recorded roster. Hex, no prefix, like a scenario digest."""
    canon = json.dumps(dict(roster), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def roster_holds(roster: Mapping | None, digest: str | None) -> bool:
    """Whether a recorded roster still reads as recorded. Neither recorded: nothing to hold."""
    if roster is None and digest is None:
        return True
    return roster is not None and digest is not None and roster_digest(roster) == digest


def recorded_agents(roster: Mapping, scope: Collection[str] | None) -> list[PartitionAgent]:
    """The agents a recorded roster names, each with its granted modules in scope."""
    modules: dict[str, set[str]] = {}
    for grant in roster.get("grants") or ():
        if scope is not None and grant["module_id"] not in scope:
            continue
        modules.setdefault(grant["agent_id"], set()).add(grant["module_id"])
    return [PartitionAgent(a, tuple(sorted(m))) for a, m in sorted(modules.items())]


async def partition_roster(
    session: AsyncSession,
    *,
    venture_id: str,
    forge_id: str,
    scope: Collection[str] | None,
    recorded: Mapping | None = None,
) -> list[PartitionAgent]:
    """The agents who sit the partition, sorted by agent id.

    `recorded` is the partition's roster (ADR-0162). When given it is the whole answer:
    its grants' agents, and no run is read.

    Otherwise `scope` is the partition's module set. An agent with no module in it is
    not on the roster: the partition has nothing to put to it (ADR-0152).
    `None` - a partition authored before ADR-0125 recorded its modules - keeps
    the ADR-0110 roster, every agent with a run; such a partition is never
    graded, and its verdict reads as it always did.
    """
    if recorded is not None:
        return recorded_agents(recorded, scope)
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
    "REFUSED_ROSTER_ELSEWHERE",
    "REFUSED_ROSTER_EMPTY",
    "REFUSED_ROSTER_INVALID",
    "REFUSED_ROSTER_REPEATS",
    "PartitionAgent",
    "RosterRefused",
    "RosterStatement",
    "partition_roster",
    "record_roster",
    "recorded_agents",
    "roster_digest",
    "roster_holds",
    "venture_of_run_ref",
]
