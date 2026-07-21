"""Execute a scenario run end-to-end and persist it (blueprint §C.9 orchestration).

Flow: resolve scenario/pack/agent → create Run → CCB pre → run state machine →
persist transcript + trace + CCB post → set status. Deterministic via scenario.seed.

Run.status here reflects *execution* outcome (passed/failed/errored). The certification
pass/fail is the readiness gate's job (Phase 5), recorded on the Scorecard.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from src.models.agent import Agent
from src.models.pack import Pack, Scenario
from src.models.run import Run, TraceEvent
from src.services.agent_runtime.llm_client import LLMProvider, get_llm_provider
from src.services.agent_runtime.runtime import AgentRuntime
from src.services.forges import Fault, FaultType, get_forge_adapter
from src.services.forges.capitalforge import LocalCapitalForgeAdapter
from src.services.forges.registry import forge_of_cap
from src.services.forges.visionaudioforge import LocalVAFAdapter
from src.services.mock_world.world import MockWorld
from src.services.scenario_engine.complications import ComplicationInjector
from src.services.scenario_engine.runner import ScenarioRunner
from src.services.scenario_engine.state import Phase, TraceEntry
from src.services.village.ccb_store import capture_ccb
from src.services.village.reader import VillageReader, VillageReaderError
from src.utils.time import utcnow

# Deterministic fault per CapitalForge bank module.
_BANK_FAULT = {
    "emd": (FaultType.FRAUD_FLAG, "P1", "EMD release held pending fraud review"),
    "wire": (FaultType.NSF, "P0", "Wire failed: insufficient funds"),
    "bank": (FaultType.DECLINATION, "P1", "Credit application declined"),
    "deals": (FaultType.DECLINATION, "P1", "Financing declined for the deal"),
}


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


async def _run_capitalforge(state, caps, run_id: str, inject: bool) -> None:
    # Registry is the swap point (Local ↔ real HTTP); the bank ops are forge-specific.
    adapter = cast(LocalCapitalForgeAdapter, get_forge_adapter("capitalforge"))
    tenant = await adapter.provision_sandbox_tenant(run_id)
    for cap in caps:
        module = cap.split(".")[1] if "." in cap else "bank"
        if inject and module in _BANK_FAULT:
            ftype, sev, detail = _BANK_FAULT[module]
            await adapter.inject_fault(tenant.tenant_id, Fault(ftype, sev, detail, module))
        if module == "emd":
            result = await adapter.emd_release(tenant.tenant_id, 10_000.0)
        elif module == "wire":
            result = await adapter.wire(tenant.tenant_id, 300_000.0)
        else:
            result = await adapter.apply(tenant.tenant_id, 200_000.0)
        _emit_forge_trace(state, "capitalforge", module, cap, result)
    await adapter.teardown_sandbox_tenant(tenant.tenant_id)


async def _run_vaf(state, caps, run_id: str, inject: bool) -> None:
    # Registry is the swap point (Local ↔ real HTTP); the doc ops are forge-specific.
    adapter = cast(LocalVAFAdapter, get_forge_adapter("vaf"))
    tenant = await adapter.provision_sandbox_tenant(run_id)
    for cap in caps:
        module = cap.split(".")[1] if "." in cap else "doc_vault"
        # A retrieved document may be forged/expired/revoked — VAF's OCR surfaces it.
        fault_type = FaultType.FORGED_SIGNATURE if inject else None
        result = await adapter.generate_and_extract(tenant.tenant_id, "title_report", fault_type)
        _emit_forge_trace(state, "vaf", module, cap, result)
    await adapter.teardown_sandbox_tenant(tenant.tenant_id)


async def _run_forge_side_effects(state, scenario, run_id: str) -> None:
    """Provision Forge sandbox tenants for the tested caps, run ops, record trace events.

    A fault is injected deterministically (advanced-crisis tier OR even seed) so faults →
    Software Gaps are exercised; real sandbox faults come from the live Forge. Sandbox-isolated:
    no Village writes."""
    caps = scenario.testedForgeCaps or []
    inject = scenario.tier == "advanced_crisis" or scenario.seed % 2 == 0
    cf = [c for c in caps if forge_of_cap(c) == "capitalforge"]
    vaf = [c for c in caps if forge_of_cap(c) == "vaf"]
    if cf:
        await _run_capitalforge(state, cf, run_id, inject)
    if vaf:
        await _run_vaf(state, vaf, run_id, inject)


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


async def run_scenario(
    session: AsyncSession,
    scenario_id: str,
    reader: VillageReader,
    provider: LLMProvider | None = None,
    *,
    blind_mode: bool = False,
) -> Run:
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

    run = Run(
        runId=str(ULID()),
        scenarioId=scenario.id,
        packId=pack.id,
        agentId=agent.id,
        executionMode=pack.executionModeDefault,
        narrativeMode=pack.narrativeModeDefault,
        blindMode=blind_mode,
        status="running",
        startedAt=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()

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
    runner = ScenarioRunner(
        scenario=scenario_dict,
        agent_runtime=runtime,
        mock_world=world,
        complication_injector=injector,
        seed=scenario.seed,
        fallback_name=agent.name,
        fallback_role=agent.role,
    )

    try:
        state = await runner.run(run.runId, agent.villageAgentId)
    except Exception as exc:  # noqa: BLE001 — a failed run is data, not a crash
        run.status = "errored"
        run.outcome = f"error: {type(exc).__name__}"
        run.endedAt = datetime.now(UTC)
        await session.commit()
        await session.refresh(run)
        return run

    # Forge side-effects (CapitalForge Mock Bank + VAF Doc Vault) → trace events
    # (faults become Software Gaps).
    await _run_forge_side_effects(state, scenario, run.runId)

    # Persist results
    run.transcript = state.transcript
    run.tokensUsed = state.tokens_used
    run.costUsd = 0.0  # StubProvider is free; real providers set a metered cost.
    run.latencyMs = int(state.elapsed_seconds() * 1000)
    run.outcome = state.outcome
    run.status = _OUTCOME_STATUS.get(state.outcome or "", "errored")
    run.endedAt = datetime.now(UTC)

    for entry in state.trace:
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

    run.ccbPostId = await _maybe_capture_ccb(session, reader, agent.villageAgentId, "post")

    await session.commit()
    await session.refresh(run)
    return run
