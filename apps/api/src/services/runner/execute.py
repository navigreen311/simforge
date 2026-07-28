"""Execute a scenario run end-to-end and persist it (blueprint §C.9 orchestration).

Flow: resolve scenario/pack/agent → create Run → CCB pre → run state machine →
persist transcript + trace + CCB post → set status. Deterministic via scenario.seed.

Run.status here reflects *execution* outcome (passed/failed/errored). The certification
pass/fail is the readiness gate's job (Phase 5), recorded on the Scorecard.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from src.models.agent import Agent
from src.models.pack import Pack, Scenario
from src.models.run import Run, TraceEvent
from src.services.agent_runtime.llm_client import LLMProvider, get_llm_provider
from src.services.agent_runtime.runtime import AgentRuntime
from src.services.forges import FaultType, get_forge_adapter
from src.services.forges.registry import forge_of_cap
from src.services.mock_world.world import MockWorld
from src.services.scenario_engine.complications import ComplicationInjector
from src.services.scenario_engine.runner import ScenarioRunner
from src.services.scenario_engine.state import Phase, TraceEntry
from src.services.village.ccb_store import capture_ccb
from src.services.village.reader import VillageReader, VillageReaderError
from src.telemetry.tracing import span
from src.utils.time import utcnow

# Which fault to inject when exercising a forge cap (test policy lives here; how to exercise
# lives in each adapter's `exercise`). Keyed forge → module → fault_type, with a per-forge
# default for modules not listed. This is the runner's only forge-specific knowledge now — the
# adapter (Local or HTTP, per FORGE_MODE) does the rest through the uniform `exercise` op.
_FORGE_MODULE_FAULT: dict[str, dict[str, str]] = {
    "capitalforge": {
        "emd": FaultType.FRAUD_FLAG,
        "wire": FaultType.NSF,
        "bank": FaultType.DECLINATION,
        "deals": FaultType.DECLINATION,
    },
    "medlink-pro": {
        "scheduler": FaultType.SHIFT_DOUBLE_BOOKED,
        "compliance": FaultType.CREDENTIAL_EXPIRED_UNFLAGGED,
        "clinician": FaultType.CREDENTIAL_EXPIRED_UNFLAGGED,
    },
    "funnelforge": {
        "leads": FaultType.WEBHOOK_DROPPED,
        "campaigns": FaultType.CAMPAIGN_TO_UNSUBSCRIBED,
        "sequences": FaultType.SEQUENCE_MISFIRE,
        "segments": FaultType.SEGMENT_STALE,
    },
}
_FORGE_DEFAULT_FAULT: dict[str, str] = {
    "capitalforge": FaultType.DECLINATION,
    "vaf": FaultType.FORGED_SIGNATURE,
    "voiceforge": FaultType.DROPPED_CALL,
    "cre-forge": FaultType.TITLE_DEFECT,
    "medlink-pro": FaultType.UI_BLOCKING_MODAL,
    "funnelforge": FaultType.WEBHOOK_DROPPED,
}


def _pick_fault(forge: str, module: str) -> str | None:
    by_module = _FORGE_MODULE_FAULT.get(forge, {})
    return by_module.get(module) or _FORGE_DEFAULT_FAULT.get(forge)


def _emit_forge_trace(state, forge: str, module: str, cap: str, result: dict) -> None:
    if result.get("fault"):
        f = result["fault"]
        state.trace.append(
            TraceEntry(
                timestamp=utcnow(),
                event_type="forge_fault",
                phase=Phase.RESOLUTION.value,
                turn_number=state.turn_count,
                payload={
                    "forge": forge,
                    "module": module,
                    "severity": f["severity"],
                    "reason": result.get("reason") or f["type"],
                    "detail": f["detail"],
                    "cap": cap,
                },
            )
        )
    else:
        state.trace.append(
            TraceEntry(
                timestamp=utcnow(),
                event_type="forge_action",
                phase=Phase.RESOLUTION.value,
                turn_number=state.turn_count,
                payload={"forge": forge, "module": module, "outcome": result["outcome"]},
            )
        )


def _group_caps_by_forge(caps: list[str]) -> dict[str, list[str]]:
    """Group tested caps by forge, preserving first-appearance order (deterministic)."""
    by_forge: dict[str, list[str]] = {}
    for cap in caps:
        by_forge.setdefault(forge_of_cap(cap), []).append(cap)
    return by_forge


async def _run_forge_side_effects(state, scenario, run_id: str) -> None:
    """Provision each tested Forge's sandbox tenant, exercise the tested caps, record trace events.

    Forge-agnostic and mode-agnostic: every forge is driven through the uniform `exercise` op, so
    the same loop works whether the resolved adapter is Local (in-process engine) or HTTP (real
    sandbox, per FORGE_MODE — ADR-0016). A fault is injected deterministically (advanced-crisis
    tier OR even seed) so faults → Software Gaps are exercised. Sandbox-isolated: no Village
    writes."""
    inject = scenario.tier == "advanced_crisis" or scenario.seed % 2 == 0
    for forge, caps in _group_caps_by_forge(scenario.testedForgeCaps or []).items():
        adapter = get_forge_adapter(forge)
        try:
            tenant = await adapter.provision_sandbox_tenant(run_id)
        except NotImplementedError:
            continue  # unknown forge (Null adapter) — nothing to exercise
        for cap in caps:
            module = cap.split(".")[1] if "." in cap else "core"
            fault_type = _pick_fault(forge, module) if inject else None
            result = await adapter.exercise(tenant.tenant_id, cap, fault_type)
            _emit_forge_trace(state, forge, module, cap, result)
        await adapter.teardown_sandbox_tenant(tenant.tenant_id)


_OUTCOME_STATUS = {"resolved": "passed", "max_turns_reached": "failed", "slo_exceeded": "failed"}


class RunnerError(Exception):
    """Raised when a run cannot be started (missing scenario/agent)."""


def _load_cold_open(scenario: Scenario) -> str:
    try:
        data = yaml.safe_load(Path(scenario.yamlPath).read_text(encoding="utf-8")) or {}
        return data.get("cold_open", "")
    except OSError:
        return f"Begin the '{scenario.title}' scenario."


async def _maybe_capture_ccb(
    session: AsyncSession, reader: VillageReader, agent_village_id: str, phase: str
) -> str | None:
    try:
        row = await capture_ccb(session, reader, agent_village_id, phase)  # type: ignore[arg-type]
        return row.id
    except VillageReaderError:
        return None  # agent not present in the (dev) Village tree — run proceeds without CCB


async def resolve_run_context(
    session: AsyncSession, scenario_id: str, integrated: bool
) -> tuple[Scenario, Pack, Agent, bool]:
    """Resolve + gate a run (scenario/pack/tested-agent, integrated decision + budget)."""
    scenario = (
        await session.execute(select(Scenario).where(Scenario.scenarioId == scenario_id))
    ).scalar_one_or_none()
    if scenario is None:
        raise RunnerError(f"Scenario not found: {scenario_id}")
    pack = (await session.execute(select(Pack).where(Pack.id == scenario.packId))).scalar_one()
    agent = (
        await session.execute(
            select(Agent).where(Agent.villageAgentId == scenario.testedAgentVillageId)
        )
    ).scalar_one_or_none()
    if agent is None:
        raise RunnerError(f"Tested agent not registered: {scenario.testedAgentVillageId}")

    from src.services.execution import is_integrated_enabled

    use_integrated = is_integrated_enabled(pack.integratedRunsAllowed, integrated)

    from src.services.budget import enforce_budget

    await enforce_budget(session, "integrated" if use_integrated else "sandbox")
    return scenario, pack, agent, use_integrated


def _persist_new_trace(session: AsyncSession, run: Run, state, cursor: list[int]) -> None:
    """Persist trace entries emitted since the cursor; advance it. Shared by sync + live paths."""
    for entry in state.trace[cursor[0] :]:
        session.add(
            TraceEvent(
                runId=run.id,
                timestamp=entry.timestamp,
                eventType=entry.event_type,
                phase=entry.phase,
                turnNumber=entry.turn_number,
                payload=entry.payload,
            )
        )
    cursor[0] = len(state.trace)


async def _execute_into_run(
    session: AsyncSession,
    run: Run,
    scenario: Scenario,
    pack: Pack,
    agent: Agent,
    reader: VillageReader,
    provider: LLMProvider | None,
    use_integrated: bool,
    live: bool = False,
) -> Run:
    """Execute an already-created Run row end-to-end and persist it.

    When `live` is True (the live monitor path) transcript + new trace are persisted incrementally
    as the run proceeds so a watcher can read progress; the sync path (live=False) persists once at
    the end. Both share one trace cursor, so trace events are never double-written.
    """
    run.ccbPreId = await _maybe_capture_ccb(session, reader, agent.villageAgentId, "pre")

    provider = provider or get_llm_provider()
    runtime = AgentRuntime(village_reader=reader, provider=provider)
    world = MockWorld(persona_label=f"{pack.ownerVenture} counterparty", seed=scenario.seed)
    injector = ComplicationInjector(
        inject_at_turn=2,
        complication_text=f"An unexpected obstacle complicates '{scenario.title}'.",
    )
    scenario_dict = {
        "scenario_id": scenario.scenarioId,
        "title": scenario.title,
        "slo_seconds": scenario.sloSeconds,
        "cold_open": _load_cold_open(scenario),
    }
    cursor = [0]

    live_progress = None
    if live:

        async def live_progress(state) -> None:  # noqa: ANN001
            run.transcript = list(state.transcript)
            run.tokensUsed = state.tokens_used
            _persist_new_trace(session, run, state, cursor)
            await session.commit()

    runner = ScenarioRunner(
        scenario=scenario_dict,
        agent_runtime=runtime,
        mock_world=world,
        complication_injector=injector,
        seed=scenario.seed,
        fallback_name=agent.name,
        fallback_role=agent.role,
        on_progress=live_progress,
    )

    try:
        with span(
            "scenario.run",
            **{
                "scenario.id": scenario.scenarioId,
                "scenario.tier": scenario.tier,
                "agent.village_id": agent.villageAgentId,
                "execution.mode": run.executionMode,
            },
        ):
            state = await runner.run(run.runId, agent.villageAgentId)
    except Exception as exc:  # noqa: BLE001 — a failed run is data, not a crash
        run.status = "errored"
        run.outcome = f"error: {type(exc).__name__}"
        run.endedAt = datetime.now(UTC)
        await session.commit()
        await session.refresh(run)
        return run

    await _run_forge_side_effects(state, scenario, run.runId)

    if use_integrated:
        from src.services.execution import apply_integrated_actions

        await apply_integrated_actions(session, run, scenario, agent)

    run.transcript = state.transcript
    run.tokensUsed = state.tokens_used
    run.costUsd = 0.0  # StubProvider is free; real providers set a metered cost.
    run.latencyMs = int(state.elapsed_seconds() * 1000)
    run.outcome = state.outcome
    run.status = _OUTCOME_STATUS.get(state.outcome or "", "errored")
    run.endedAt = datetime.now(UTC)

    _persist_new_trace(session, run, state, cursor)  # persists only entries not yet written
    run.ccbPostId = await _maybe_capture_ccb(session, reader, agent.villageAgentId, "post")

    await session.commit()
    await session.refresh(run)
    return run


async def run_scenario(
    session: AsyncSession,
    scenario_id: str,
    reader: VillageReader,
    provider: LLMProvider | None = None,
    *,
    blind_mode: bool = False,
    integrated: bool = False,
    narrative_mode: str | None = None,
) -> Run:
    scenario, pack, agent, use_integrated = await resolve_run_context(
        session, scenario_id, integrated
    )
    run = Run(
        runId=str(ULID()),
        scenarioId=scenario.id,
        packId=pack.id,
        agentId=agent.id,
        executionMode="integrated" if use_integrated else "sandbox",
        narrativeMode=narrative_mode or pack.narrativeModeDefault,
        blindMode=blind_mode,
        status="running",
        startedAt=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    return await _execute_into_run(
        session, run, scenario, pack, agent, reader, provider, use_integrated
    )
