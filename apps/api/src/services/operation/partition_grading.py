"""Gate 9.5 grading: put a venture's SEALED partition to its agents, record whether (ADR-0110).

WHAT THIS DOES
==============

    For one sealed `HeldOutPartition`, find the venture's agents, put each one the
    partition's scenarios for the modules it operates, grade every answer with
    `held_out_scoring.grade_scenario`, and append ONE `HeldOutPartitionVerdict` per
    agent. PASS only if every scenario passed (`HELD_OUT_PASS_THRESHOLD` is 1.0).

WHETHER, NEVER WHY
==================

    A `ScenarioVerdict` carries reasons. They live in this process for the length
    of one agent's grading and are then dropped. Nothing here stores, logs or
    returns a reason, a count of failures, a module or a scenario id. A rich enough
    explanation of a failure reconstructs the scenario (gate-9-5-verdict.md).

NOTHING BECOMES TRAINING SIGNAL
===============================

    This module writes to `HeldOutPartitionVerdict` and nothing else. No
    `OperationCertification`, no `OperationRun` verdict, no submission, no
    instruction set, no rubric row. `test_partition_sweep` counts those tables
    before and after a graded pass.

THE ANSWER PATH IS THE BATTERY'S
================================

    The agent receives `held_out_scoring.deliver(scenario)` and nothing else of
    the scenario - the same `Probe(module_id, prompt)` the ordinary battery puts,
    under the same `battery_system_context` and the same `RESPONSE_PROTOCOL`.
    Its answer is read by `battery.parse_answer` and `battery.observe_answer`.
    An agent cannot tell a partition probe from an ordinary one by its shape.

ADR-0050
========

    Process-side only. No router may import this module; a guard test walks the
    import graph from the routers that exist to hold that true.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.base import _new_id
from src.models.forge_instruction_set import ForgeInstructionSet
from src.models.held_out_partition import (
    HeldOutPartition,
    HeldOutPartitionOutcome,
    HeldOutPartitionScenario,
    HeldOutPartitionVerdict,
)
from src.models.operation_run import OperationRun
from src.services.agent_runtime.agent_identity import check_agent_identity
from src.services.agent_runtime.examiner import check_examiner
from src.services.agent_runtime.llm_client import LLMResponse
from src.services.agent_runtime.runtime import AgentRuntime
from src.services.operation.battery import (
    BOOTSTRAP_FORGE_IDS,
    battery_system_context,
    observe_answer,
    parse_answer,
)
from src.services.operation.held_out import HeldOutScenario, obligations_from_never_do
from src.services.operation.held_out_scoring import (
    HELD_OUT_PASS_THRESHOLD,
    ProtocolViolation,
    ScenarioVerdict,
    deliver,
    grade_scenario,
)
from src.services.operation.rubric import VERDICT_FAIL, VERDICT_NOT_RUN
from src.services.village.model_config import VillageConfigError, read_village_agent_model
from src.telemetry.logging import get_logger
from src.utils.time import utcnow

log = get_logger("partition_grading")

PASS = "PASS"
FAIL = "FAIL"
NOT_RUN = "NOT_RUN"
IN_PROGRESS = "IN_PROGRESS"
TIMEOUT = "TIMEOUT"

#: Verdicts that settle an agent on a partition. It is not graded again until the
#: partition is re-sealed, which gives it a new id and a new digest.
SETTLED = frozenset({PASS, FAIL})

#: How long one agent's grading may take before it is recorded TIMEOUT. Also the
#: age at which an IN_PROGRESS row with no successor is taken as abandoned.
#: Read at call time, so a test can shorten it.
PARTITION_AGENT_BUDGET_SECONDS: float = 1800.0

#: The run-ref prefix The Office mints (`mint_run_ref`), venture in segment 2:
#: `office:{venture_id}:{forge_id}:{target}:...`. Measured, ADR-0110.
OFFICE_REF_PREFIX = "office"


# =========================================================================
# Reading the seam
# =========================================================================


def scenario_from_body(body: Mapping[str, object]) -> HeldOutScenario:
    """`HeldOutPartitionScenario.body` back into the dataclass it was written from.

    The seam (Session A): the body is `dataclasses.asdict(HeldOutScenario)` as
    JSON, so tuples arrived as lists. Only `unsupported_readings` is a tuple.
    An unknown key raises: a body this cannot read is not graded by guessing.
    """
    fields = dict(body)
    fields["unsupported_readings"] = tuple(fields.get("unsupported_readings") or ())
    return HeldOutScenario(**fields)  # type: ignore[arg-type]


def venture_of_run_ref(run_ref: str) -> str | None:
    """The venture segment of an Office-minted run ref, or None.

    The only place the operation path carries the venture (ADR-0058). A ref
    not minted by The Office names no venture and selects no agent.
    """
    parts = (run_ref or "").split(":")
    if len(parts) < 3 or parts[0] != OFFICE_REF_PREFIX or not parts[1]:
        return None
    return parts[1]


# =========================================================================
# Who is graded (ADR-0110, R3/R4)
# =========================================================================


@dataclass(frozen=True, slots=True)
class PartitionAgent:
    """One agent of a venture on a forge, and the modules it operates there.

    `agent_id` is the Village ref - the id the examiner resolves and the one
    a probe is put to (ADR-0083: `villageAgentRef`, else `agentId`).
    """

    agent_id: str
    modules: tuple[str, ...]


async def agents_for_partition(
    session: AsyncSession, partition: HeldOutPartition
) -> list[PartitionAgent]:
    """The venture's agents on the partition's forge, read off Unit-A runs.

    Nothing in the operation path has a venture column. The venture reaches
    SimForge only as segment 2 of the run ref, so that is what is matched.
    Sorted by agent id so a pass is deterministic.
    """
    rows = (
        await session.execute(
            select(
                OperationRun.runRef,
                OperationRun.moduleId,
                OperationRun.agentId,
                OperationRun.villageAgentRef,
            ).where(
                OperationRun.forgeId == partition.forgeId,
                OperationRun.unit == "A",
                OperationRun.moduleId.is_not(None),
                OperationRun.agentId.is_not(None),
            )
        )
    ).all()
    modules: dict[str, set[str]] = {}
    for run_ref, module_id, agent_id, village_ref in rows:
        if venture_of_run_ref(run_ref) != partition.ventureId:
            continue
        who = village_ref or agent_id
        modules.setdefault(who, set()).add(module_id)
    return [PartitionAgent(a, tuple(sorted(m))) for a, m in sorted(modules.items())]


async def current_instruction_set(
    session: AsyncSession, forge_id: str, module_id: str
) -> ForgeInstructionSet | None:
    """The forge's CURRENT instruction set for a module: the newest (R3).

    Not a run's set: a partition is graded against the venture's scope now,
    not against the curriculum some earlier run was opened under.
    """
    return (
        await session.execute(
            select(ForgeInstructionSet)
            .where(
                ForgeInstructionSet.forgeId == forge_id,
                ForgeInstructionSet.moduleId == module_id,
            )
            # The same order ADR-0109's author reads "current" by.
            .order_by(ForgeInstructionSet.createdAt.desc(), ForgeInstructionSet.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


# =========================================================================
# Putting the partition and folding the verdicts
# =========================================================================


@dataclass(frozen=True, slots=True)
class ModulePlan:
    """What one module's probes are put under: its scenarios and its rulebook."""

    module_id: str
    scenarios: tuple[HeldOutScenario, ...]
    never_do: tuple[str, ...]
    sections: Mapping[str, str] | None = None
    #: The stored rows the scenarios came from, in the same order (ADR-0114).
    #: A reference for the outcome record; never content.
    scenario_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProbeOutcome:
    """One probe's outcome, kept with the verdict (ADR-0114). No content.

    `answer_state` says how the answer arrived, so a FAIL can be told apart
    from a model that never answered: `answered`, `empty` (nothing came
    back), `unparseable` (text outside the protocol), `provider_error`.
    """

    scenario_id: str | None
    module_id: str
    scenario_class: str
    outcome: str
    failure_modes: tuple[str, ...]
    answer_state: str
    tokens_output: int | None = None
    latency_ms: int | None = None


def agent_verdict(verdicts: Sequence[ScenarioVerdict]) -> str:
    """One agent's verdict from its scenario verdicts. Whether, never why.

    nothing put          -> NOT_RUN
    any FAIL             -> FAIL
    any NOT_RUN          -> NOT_RUN  (not a pass, not a failure)
    pass rate < 1.0      -> FAIL
    otherwise            -> PASS
    """
    if not verdicts:
        return NOT_RUN
    if any(v.verdict == VERDICT_FAIL for v in verdicts):
        return FAIL
    if any(v.verdict == VERDICT_NOT_RUN for v in verdicts):
        return NOT_RUN
    rate = sum(1 for v in verdicts if v.passed) / len(verdicts)
    return PASS if rate >= HELD_OUT_PASS_THRESHOLD else FAIL


async def put_partition(
    *,
    agent_id: str,
    plans: Sequence[ModulePlan],
    runtime: AgentRuntime,
    seed: int = 0,
    outcomes: list[ProbeOutcome] | None = None,
) -> str:
    """Put every planned scenario to one agent, grade each, fold to one verdict.

    The agent sees `deliver(scenario).prompt` under the battery's operating
    context. A provider failure is NOT_RUN for that probe, never a FAIL; a
    protocol violation is a FAIL naming the rule (ADR-0063).

    ADR-0114: each probe's outcome is appended to `outcomes` as it is
    graded - the caller's list, so the probes graded before a timeout are
    still there to keep. Codes and counts only; the answer text is not.
    """
    sink: list[ProbeOutcome] = outcomes if outcomes is not None else []
    graded: list[ScenarioVerdict] = []
    for plan in plans:
        refs = tuple(ob.ref for ob in obligations_from_never_do(plan.module_id, plan.never_do))
        context = battery_system_context(plan.module_id, plan.never_do, plan.sections)
        for i, scenario in enumerate(plan.scenarios):
            sid = plan.scenario_ids[i] if i < len(plan.scenario_ids) else None
            probe = deliver(scenario)
            try:
                response = await runtime.turn(
                    agent_id,
                    [{"role": "scenario", "content": probe.prompt}],
                    seed,
                    extra_system=context,
                )
            except Exception:  # noqa: BLE001 - never put is NOT_RUN, never FAIL
                verdict = grade_scenario(scenario, None)
                graded.append(verdict)
                sink.append(_outcome(sid, plan.module_id, verdict, "provider_error"))
                continue
            answer = parse_answer(response.content)
            if isinstance(answer, ProtocolViolation):
                verdict = grade_scenario(scenario, None, violation=answer)
                state = "empty" if not response.content.strip() else "unparseable"
            else:
                observed = observe_answer(
                    answer, probed_ref=scenario.obligation_ref, declared_refs=refs
                )
                verdict = grade_scenario(scenario, observed)
                state = "answered"
            graded.append(verdict)
            sink.append(_outcome(sid, plan.module_id, verdict, state, response))
    return agent_verdict(graded)


def _outcome(
    scenario_id: str | None,
    module_id: str,
    verdict: ScenarioVerdict,
    answer_state: str,
    response: LLMResponse | None = None,
) -> ProbeOutcome:
    return ProbeOutcome(
        scenario_id=scenario_id,
        module_id=module_id,
        scenario_class=verdict.scenario_class,
        outcome=verdict.verdict,
        failure_modes=tuple(verdict.reasons) if not verdict.passed else (),
        answer_state=answer_state,
        tokens_output=response.tokens_output if response is not None else None,
        latency_ms=response.latency_ms if response is not None else None,
    )


def instructions_digest(sets: Sequence[ForgeInstructionSet]) -> str | None:
    """The instruction sets an agent was graded under, as one value.

    One set: its own `contentHash`. Several: `set:sha256:` over the sorted
    `module=hash` pairs. None when nothing was put.
    """
    if not sets:
        return None
    if len(sets) == 1:
        return sets[0].contentHash
    pairs = sorted(f"{s.moduleId}={s.contentHash}" for s in sets)
    return "set:sha256:" + hashlib.sha256("\n".join(pairs).encode()).hexdigest()


# =========================================================================
# The verdict rows
# =========================================================================


async def latest_verdict(
    session: AsyncSession, partition_id: str, digest: str, agent_id: str
) -> HeldOutPartitionVerdict | None:
    """The agent's latest verdict on THIS partition at THIS digest.

    Plain ids, not the ORM row: a commit expires it, and a lazy refresh
    under an async session raises.
    """
    return (
        await session.execute(
            select(HeldOutPartitionVerdict)
            .where(
                HeldOutPartitionVerdict.partitionId == partition_id,
                HeldOutPartitionVerdict.agentId == agent_id,
                HeldOutPartitionVerdict.partitionDigest == digest,
            )
            .order_by(HeldOutPartitionVerdict.decidedAt.desc(), HeldOutPartitionVerdict.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


_ONE_MS = timedelta(milliseconds=1)


@dataclass
class _Ledger:
    """Appends one partition's verdict rows, each committed on its own.

    Append-only: no row is ever updated. `decidedAt` is kept strictly
    increasing per agent - `utcnow()` has millisecond precision, and an
    IN_PROGRESS and its verdict written in one millisecond would tie on
    the column that says which is latest.
    """

    session: AsyncSession
    partition_id: str
    venture_id: str
    digest: str
    recorded: int = 0

    async def append(
        self,
        agent_id: str,
        verdict: str,
        after: datetime | None,
        instruction_hash: str | None = None,
        outcomes: Sequence[ProbeOutcome] = (),
    ) -> datetime:
        at = utcnow()
        if after is not None and at <= after:
            at = after + _ONE_MS
        row = HeldOutPartitionVerdict(
            id=_new_id(),
            partitionId=self.partition_id,
            ventureId=self.venture_id,
            agentId=agent_id,
            verdict=verdict,
            partitionDigest=self.digest,
            instructionContentHash=instruction_hash,
            decidedAt=at,
        )
        self.session.add(row)
        # Flushed before its outcomes: they reference it, and no relationship
        # tells the unit of work to insert it first. Postgres refused the other
        # order. Still one commit, so neither can exist without the other.
        await self.session.flush()
        # ADR-0114. The why, in the same commit as the whether: a verdict
        # without its outcomes, or outcomes without their verdict, cannot exist.
        for o in outcomes:
            if o.scenario_id is None:
                continue
            self.session.add(
                HeldOutPartitionOutcome(
                    verdictId=row.id,
                    partitionId=self.partition_id,
                    agentId=agent_id,
                    scenarioId=o.scenario_id,
                    moduleId=o.module_id,
                    scenarioClass=o.scenario_class,
                    outcome=o.outcome,
                    failureModes=list(o.failure_modes),
                    answerState=o.answer_state,
                    tokensOutput=o.tokens_output,
                    latencyMs=o.latency_ms,
                )
            )
        await self.session.commit()
        self.recorded += 1
        return at


# =========================================================================
# The examiner, and one partition
# =========================================================================


async def examiner_runtime(runtime: AgentRuntime) -> AgentRuntime | str:
    """The runtime at the Village's declared settings, or the examiner's refusal.

    The same two steps `battery_for_run` takes (ADR-0061, ADR-0062): read the
    declared settings first, then check the pinned model. A refusal is a named
    string and the pass puts nothing.
    """
    try:
        declared = read_village_agent_model().settings
    except VillageConfigError:
        declared = {}
    at_production = replace(runtime, generation=dict(declared)) if declared else runtime
    check = check_examiner(await at_production.model_identity())
    if not check.ok:
        return check.reason or "examiner_refused"
    return at_production


@dataclass(frozen=True, slots=True)
class PartitionOutcome:
    """What one partition's grading did. Counts only: no verdicts, no reasons."""

    partition_id: str
    agents: int
    put: int
    recorded: int
    skipped: str | None = None


SKIP_NOT_SEALED = "the_partition_is_not_sealed"
SKIP_BOOTSTRAP = "this_forge_is_certified_by_a_human_bootstrap"


async def _plans_for(
    session: AsyncSession,
    runtime: AgentRuntime,
    forge_id: str,
    agent: PartitionAgent,
    by_module: Mapping[str, Sequence[HeldOutScenario]],
) -> tuple[list[ModulePlan], list[ForgeInstructionSet]] | None:
    """What this agent would be put, or None when nothing can be put.

    None when: no module it operates has scenarios, the Village cannot name
    it (ADR-0061 ruling 2), or a module has no current never-do list to
    number the rules by. Each of those is NOT_RUN, never a pass.
    """
    in_scope = [m for m in agent.modules if m in by_module]
    if not in_scope:
        return None
    if not check_agent_identity(runtime.village_reader, agent.agent_id).ok:
        return None
    plans: list[ModulePlan] = []
    sets: list[ForgeInstructionSet] = []
    for module_id in in_scope:
        iset = await current_instruction_set(session, forge_id, module_id)
        if iset is None or not iset.neverDo:
            return None
        sets.append(iset)
        plans.append(
            ModulePlan(
                module_id=module_id,
                scenarios=tuple(by_module[module_id]),
                never_do=tuple(iset.neverDo),
                sections=iset.sections,
            )
        )
    return plans, sets


async def grade_partition(
    session: AsyncSession,
    partition_id: str,
    *,
    runtime: AgentRuntime,
    seed: int = 0,
    limit: int | None = None,
    budget_seconds: float | None = None,
) -> PartitionOutcome:
    """Grade one partition for every agent that is due. Sealed only.

    DUE: no verdict yet, or NOT_RUN / TIMEOUT last time. PASS and FAIL settle.
    An IN_PROGRESS younger than the budget is left alone; an older one was
    abandoned and gets a TIMEOUT row before the agent is put again.

    A cheap NOT_RUN (no module in scope, unidentifiable agent, no instruction
    set) is written only if the latest verdict is not already NOT_RUN, so an
    hourly pass does not grow the table for an agent nothing can be put to.

    `limit` caps the agents actually PUT (the paid part). `runtime` must
    already be the examiner's (`examiner_runtime`).
    """
    budget = PARTITION_AGENT_BUDGET_SECONDS if budget_seconds is None else budget_seconds
    partition = await session.get(HeldOutPartition, partition_id)
    if partition is None or partition.status != "sealed" or not partition.contentDigest:
        return PartitionOutcome(partition_id, 0, 0, 0, skipped=SKIP_NOT_SEALED)
    if partition.forgeId in BOOTSTRAP_FORGE_IDS:
        return PartitionOutcome(partition_id, 0, 0, 0, skipped=SKIP_BOOTSTRAP)

    # Plain values out BEFORE any commit: a commit expires the ORM object.
    pid, forge, digest = partition.id, partition.forgeId, partition.contentDigest
    ledger = _Ledger(session, pid, partition.ventureId, digest)
    scenario_rows = (
        (
            await session.execute(
                select(HeldOutPartitionScenario)
                .where(HeldOutPartitionScenario.partitionId == pid)
                .order_by(HeldOutPartitionScenario.moduleId, HeldOutPartitionScenario.id)
            )
        )
        .scalars()
        .all()
    )
    by_module: dict[str, list[HeldOutScenario]] = {}
    ids_by_module: dict[str, list[str]] = {}
    for row in scenario_rows:
        by_module.setdefault(row.moduleId, []).append(scenario_from_body(row.body))
        ids_by_module.setdefault(row.moduleId, []).append(row.id)

    agents = await agents_for_partition(session, partition)

    put = 0
    for agent in agents:
        if limit is not None and put >= limit:
            break
        latest = await latest_verdict(session, pid, digest, agent.agent_id)
        last = latest.verdict if latest is not None else None
        last_at = latest.decidedAt if latest is not None else None
        if last in SETTLED:
            continue
        if last == IN_PROGRESS and last_at is not None:
            if last_at > utcnow() - timedelta(seconds=budget):
                continue
            last_at = await ledger.append(agent.agent_id, TIMEOUT, last_at)
            last = TIMEOUT

        planned = await _plans_for(session, runtime, forge, agent, by_module)
        if planned is None:
            if last != NOT_RUN:
                await ledger.append(agent.agent_id, NOT_RUN, last_at)
            continue
        plans, sets = planned
        plans = [
            replace(p, scenario_ids=tuple(ids_by_module.get(p.module_id, ()))) for p in plans
        ]

        instruction_hash = instructions_digest(sets)
        last_at = await ledger.append(agent.agent_id, IN_PROGRESS, last_at, instruction_hash)
        put += 1
        outcomes: list[ProbeOutcome] = []
        try:
            verdict = await asyncio.wait_for(
                put_partition(
                    agent_id=agent.agent_id,
                    plans=plans,
                    runtime=runtime,
                    seed=seed,
                    outcomes=outcomes,
                ),
                timeout=budget,
            )
        except TimeoutError:
            # The probes graded before the budget ran out are kept (ADR-0114).
            verdict = TIMEOUT
        except Exception as exc:  # noqa: BLE001 - one agent must not end the pass
            await session.rollback()
            log.warning("partition_agent_not_graded", error=type(exc).__name__)
            verdict = NOT_RUN
            outcomes = []
        await ledger.append(agent.agent_id, verdict, last_at, instruction_hash, outcomes)
        # The verdict is logged; never a reason, a module or a scenario.
        log.info("partition_agent_graded", partition=pid, agent=agent.agent_id, verdict=verdict)

    return PartitionOutcome(pid, len(agents), put, ledger.recorded)


__all__ = [
    "FAIL",
    "IN_PROGRESS",
    "NOT_RUN",
    "PARTITION_AGENT_BUDGET_SECONDS",
    "PASS",
    "TIMEOUT",
    "ModulePlan",
    "PartitionAgent",
    "ProbeOutcome",
    "PartitionOutcome",
    "agent_verdict",
    "agents_for_partition",
    "current_instruction_set",
    "examiner_runtime",
    "grade_partition",
    "put_partition",
    "scenario_from_body",
    "venture_of_run_ref",
]
