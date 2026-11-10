"""Record a sandbox run step by step and grade each turn (ADR-0166 stage 5).

A sandbox run is opened for one seed's world and a fixed list of that world's tasks. Each step a
task takes in the sandbox (`STEPS`) is recorded in order as a `SandboxStep`:

- **filed**, **claimed**: by the starter (on whose behalf the run files) and the agent the
  sandbox grant names.
- **turn_a**: the agent's ACT before any call, graded by `grade_submitted` against the task's
  Turn A key. Anything but PROCEED ends the task: nothing is called.
- **proposed**, **approved**: the governed call as a proposal, then its approval, which only
  `sandbox-approver` may give.
- **forge_answer**: what the sandbox Forge answered (`status` and the body), kept as the fields
  the task predicted (`forge_fields`) and compared with the prediction; `forgeMatches` says
  whether they agree.
- **turn_b**: the agent's ACT and RECORD on that answer, graded against the Turn B key. If the
  Forge answered something else than predicted, the key was written for an answer the agent never
  saw, so the turn is NOT_GRADED with `forge_answer_differs_from_prediction`: a miss on the
  Forge's side, never the agent's.

The expected answers are the generator's (`deal_desk_world`), regenerated from the seed. A run
records the generator version and both digests when it opens, and no turn is graded once the
generator in force would give other tasks (`generator_moved`).

**Practice, never evidence** (ADR-0166 rulings 1 and 5). This module writes `SandboxRun` and
`SandboxStep` and nothing else, and it reaches no exam, certification, tier, partition, gate,
promotion streak or safe mode. `test_a_sandbox_run_reaches_no_exam_or_certification` walks its
imports and counts every table before and after a run.

Answers arrive structured, as The Office's task loop records them: an act, a record
`{subject, claim}` or null, and caveats; or `{"unreadable": <protocol rule>}`. No prose is read.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from src.models.sandbox_run import STEPS, SandboxRun, SandboxStep
from src.services.forges.deal_desk_world import (
    GENERATOR_VERSION,
    Task,
    TurnKey,
    forge_differs,
    forge_fields,
    generate_tasks,
    generate_world,
    tasks_digest,
    world_digest,
    world_name,
)
from src.services.operation.held_out_scoring import ProtocolViolation
from src.services.operation.submitted_scoring import SubmittedKey, grade_submitted
from src.utils.time import utcnow

#: Who may start a run, or own a schedule (ADR-0166 ruling 4).
STARTERS: tuple[str, ...] = ("Ivan Green", "Ira Green")
#: The ventures a sandbox Forge exists for, and that Forge. Greenstone first (9 November).
SANDBOX_FORGES: Mapping[str, str] = {"greenstone": "cre-forge"}
#: Ruled for the schedule (9 November): at most 60 tasks per run.
MAX_TASKS = 60
#: The only actor that approves a proposal in the sandbox (ADR-0166 section 3, step 5).
SANDBOX_APPROVER = "sandbox-approver"
ACT_PROCEED = "PROCEED"

VERDICT_NOT_GRADED = "NOT_GRADED"
REASON_FORGE_DIFFERS = "forge_answer_differs_from_prediction"


class SandboxRefused(ValueError):
    """A step or run the record will not write. `code` names why; nothing was written."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass(frozen=True)
class TurnAnswer:
    """One agent turn as The Office recorded it. `grade_submitted` reads it by attribute."""

    act: str
    record: tuple[str, str] | None = None
    caveats: tuple[str, ...] = ()


def submitted_key(turn: TurnKey) -> SubmittedKey:
    """A generator turn as an approved key is written, field for field."""
    return SubmittedKey(
        scenario_class=turn.scenario_class,
        module_id=turn.module_id,
        instruction_section=turn.instruction_section,
        ordinal=turn.ordinal,
        situation=turn.situation,
        expected_act=turn.expected_act,
        expected_record=turn.expected_record,
        record_subject=turn.record_subject,
        record_claim=turn.record_claim,
        record_claim_options=turn.record_claim_options,
        expected_caveat=turn.expected_caveat,
        acceptable_acts=turn.acceptable_acts,
    )


def read_answer(payload: Mapping[str, Any]) -> TurnAnswer | ProtocolViolation:
    """A turn's payload as the grader reads it. An unknown protocol rule is refused, not guessed."""
    if "unreadable" in payload:
        try:
            return ProtocolViolation(str(payload["unreadable"]))
        except ValueError as exc:
            raise SandboxRefused("unknown_protocol_rule", str(payload["unreadable"])) from exc
    act = payload.get("act")
    if not isinstance(act, str) or not act:
        raise SandboxRefused("answer_has_no_act")
    record = payload.get("record")
    pair = None
    if record is not None:
        if not isinstance(record, Mapping) or not {"subject", "claim"} <= set(record):
            raise SandboxRefused("record_not_subject_and_claim")
        pair = (str(record["subject"]), str(record["claim"]))
    caveats = tuple(str(c) for c in payload.get("caveats") or ())
    return TurnAnswer(act=act, record=pair, caveats=caveats)


def tasks_of(run: SandboxRun) -> dict[str, Task]:
    tasks = generate_tasks(generate_world(run.seed))
    if run.generatorVersion != GENERATOR_VERSION or tasks_digest(tasks) != run.tasksDigest:
        raise SandboxRefused(
            "generator_moved",
            f"run opened under {run.generatorVersion}, generator in force {GENERATOR_VERSION}",
        )
    return {t.task_id: t for t in tasks}


async def open_run(
    db: AsyncSession,
    *,
    venture: str,
    seed: int,
    started_by: str,
    task_ids: Sequence[str] | None = None,
    schedule_owner: str | None = None,
) -> SandboxRun:
    """Open a sandbox run on `seed`'s world: every task, or the ones named, in order."""
    if started_by not in STARTERS:
        raise SandboxRefused("not_a_starter", started_by)
    if schedule_owner is not None and schedule_owner not in STARTERS:
        raise SandboxRefused("not_a_schedule_owner", schedule_owner)
    if venture not in SANDBOX_FORGES:
        raise SandboxRefused("no_sandbox_forge_for_venture", venture)
    world = generate_world(seed)
    tasks = generate_tasks(world)
    known = [t.task_id for t in tasks]
    chosen = list(task_ids) if task_ids is not None else known
    if not chosen:
        raise SandboxRefused("no_tasks")
    if len(chosen) > MAX_TASKS:
        raise SandboxRefused("over_task_cap", f"{len(chosen)} > {MAX_TASKS}")
    if len(set(chosen)) != len(chosen):
        raise SandboxRefused("task_named_twice")
    unknown = [t for t in chosen if t not in known]
    if unknown:
        raise SandboxRefused("unknown_task", ", ".join(unknown))
    run = SandboxRun(
        runRef=f"sandbox-{ULID()}",
        venture=venture,
        forgeId=SANDBOX_FORGES[venture],
        seed=seed,
        generatorVersion=GENERATOR_VERSION,
        worldName=world_name(seed),
        worldDigest=world_digest(world),
        tasksDigest=tasks_digest(tasks),
        taskIds=chosen,
        startedBy=started_by,
        scheduleOwner=schedule_owner,
        status="open",
        startedAt=utcnow(),
    )
    db.add(run)
    await db.commit()
    return run


async def _steps(db: AsyncSession, run: SandboxRun) -> list[SandboxStep]:
    stmt = select(SandboxStep).where(SandboxStep.sandboxRunId == run.id).order_by(SandboxStep.seq)
    return list((await db.execute(stmt)).scalars())


def task_ended(steps: Sequence[SandboxStep]) -> bool:
    """A task ends at Turn B, or at a Turn A that called nothing."""
    if not steps:
        return False
    last = steps[-1]
    return last.step == "turn_b" or (
        last.step == "turn_a" and (last.payload or {}).get("act") != ACT_PROCEED
    )


async def record_step(
    db: AsyncSession,
    run: SandboxRun,
    *,
    task_id: str,
    step: str,
    at: datetime,
    actor: str,
    payload: Mapping[str, Any] | None = None,
    sandbox_ids: Mapping[str, str] | None = None,
    agent_id: str | None = None,
) -> SandboxStep:
    """Record one step of one task, in order, and grade it if it is a turn."""
    if run.status != "open":
        raise SandboxRefused("run_closed", run.runRef)
    if task_id not in run.taskIds:
        raise SandboxRefused("task_not_in_run", task_id)
    if step not in STEPS:
        raise SandboxRefused("unknown_step", step)
    task = tasks_of(run)[task_id]
    steps = await _steps(db, run)
    mine = [s for s in steps if s.taskId == task_id]
    if task_ended(mine):
        raise SandboxRefused("task_ended", task_id)
    expected = STEPS[len(mine)]
    if step != expected:
        raise SandboxRefused("step_out_of_order", f"{task_id}: {step}, expected {expected}")

    claimed = next((s.agentId for s in mine if s.step == "claimed"), None)
    if step == "claimed":
        if not agent_id:
            raise SandboxRefused("claim_names_no_agent", task_id)
        claimed = agent_id
    elif agent_id is not None and agent_id != claimed:
        raise SandboxRefused("agent_is_not_the_claimant", task_id)
    if step == "filed" and actor not in (run.startedBy, run.scheduleOwner):
        raise SandboxRefused("filed_by_someone_else", actor)
    if step == "approved" and actor != SANDBOX_APPROVER:
        raise SandboxRefused("approved_by_someone_else", actor)

    body = dict(payload or {})
    verdict: str | None = None
    reasons: list[str] | None = None
    forge_matches: bool | None = None
    if step == "turn_a":
        graded = grade_submitted(submitted_key(task.turn_a), read_answer(body))
        verdict, reasons = graded.verdict, list(graded.reasons)
    elif step == "forge_answer":
        # The payload is the Forge's response: `status` and its body. Only the fields the task
        # predicted are kept: what was read, not the whole response.
        differ = forge_differs(task, body)
        body = forge_fields(task, body)
        forge_matches = not differ
        reasons = [f"forge_field_differs:{k}" for k in differ]
    elif step == "turn_b":
        answer = read_answer(body)
        if not mine[-1].forgeMatches:
            verdict, reasons = VERDICT_NOT_GRADED, [REASON_FORGE_DIFFERS]
        else:
            graded = grade_submitted(submitted_key(task.turn_b), answer)
            verdict, reasons = graded.verdict, list(graded.reasons)

    row = SandboxStep(
        sandboxRunId=run.id,
        seq=len(steps) + 1,
        taskId=task_id,
        moduleId=task.module_id,
        step=step,
        at=at,
        actor=actor,
        agentId=claimed,
        sandboxIds=dict(sandbox_ids or {}),
        payload=body,
        verdict=verdict,
        reasons=reasons,
        forgeMatches=forge_matches,
        recordedAt=utcnow(),
    )
    db.add(row)
    await db.commit()
    return row


def _tally() -> dict[str, Any]:
    return {
        "tasks": 0,
        "ended": 0,
        "turn_a": {"PASS": 0, "FAIL": 0},
        "turn_b": {"PASS": 0, "FAIL": 0, VERDICT_NOT_GRADED: 0},
        "forge_mismatches": 0,
    }


def totals(run: SandboxRun, steps: Sequence[SandboxStep]) -> dict[str, Any]:
    """Per module and per agent: tasks, tasks ended, turn verdicts, Forge mismatches."""
    by_task: dict[str, list[SandboxStep]] = {t: [] for t in run.taskIds}
    for s in steps:
        by_task[s.taskId].append(s)
    tasks = tasks_of(run)
    out: dict[str, Any] = {"all": _tally(), "module": {}, "agent": {}}
    for task_id, mine in by_task.items():
        agent = next((s.agentId for s in mine if s.agentId), None) or "unclaimed"
        buckets = (
            out["all"],
            out["module"].setdefault(tasks[task_id].module_id, _tally()),
            out["agent"].setdefault(agent, _tally()),
        )
        for b in buckets:
            b["tasks"] += 1
            b["ended"] += int(task_ended(mine))
            for s in mine:
                if s.step in ("turn_a", "turn_b") and s.verdict:
                    b[s.step][s.verdict] += 1
                if s.step == "forge_answer" and s.forgeMatches is False:
                    b["forge_mismatches"] += 1
    return out


async def close_run(db: AsyncSession, run: SandboxRun) -> SandboxRun:
    """Close the run and write its totals once. A task not ended is counted, not hidden."""
    if run.status != "open":
        raise SandboxRefused("run_closed", run.runRef)
    run.totals = totals(run, await _steps(db, run))
    run.status = "closed"
    run.endedAt = utcnow()
    await db.commit()
    return run
