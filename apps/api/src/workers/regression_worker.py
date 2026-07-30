"""Regression worker (§9.2, queue `regression`, nightly).

Re-runs every active-cert agent's certifying scenarios (fresh evidence), then detects prior-pass /
now-fail flips and auto-suspends the affected cert. The re-run step needs a VillageReader; when the
Village data is unavailable it degrades to a no-rerun sweep over existing runs (still detects flips
from prior data). Scheduled by the cadence scheduler (Part 16).
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import SessionLocal, dispose_engine
from src.models.agent import Agent
from src.models.cert import AgentCert
from src.models.pack import Scenario
from src.services.evaluation import evaluate_run
from src.services.evaluation.regression_sweep import find_and_suspend_regressions
from src.services.runner import run_scenario
from src.services.village.reader import VillageReader
from src.telemetry.logging import get_logger

log = get_logger("regression_worker")


async def _rerun_certifying_scenarios(session: AsyncSession, reader: VillageReader) -> int:
    """Re-run each scenario that covers an active cert's cap, for that cert's agent. Best-effort:
    a run that errors (e.g. missing Village data) is skipped, not fatal."""
    certs = (
        (await session.execute(select(AgentCert).where(AgentCert.status == "active")))
        .scalars()
        .all()
    )
    scenarios = (await session.execute(select(Scenario))).scalars().all()
    agents = {a.id: a for a in (await session.execute(select(Agent))).scalars().all()}
    reran = 0
    seen: set[tuple[str, str]] = set()
    for cert in certs:
        agent = agents.get(cert.agentId)
        if agent is None:
            continue
        for scenario in scenarios:
            if cert.forgeCap not in (scenario.testedForgeCaps or []):
                continue
            if scenario.testedAgentVillageId != agent.villageAgentId:
                continue
            key = (agent.villageAgentId, scenario.scenarioId)
            if key in seen:
                continue
            seen.add(key)
            try:
                run = await run_scenario(session, scenario.scenarioId, reader)
                await evaluate_run(session, run.id)
                reran += 1
            except Exception as exc:  # noqa: BLE001 — a failed re-run must not abort the sweep
                log.warning(
                    "regression_rerun_skipped", scenario=scenario.scenarioId, error=str(exc)
                )
    return reran


async def _run(rerun: bool) -> dict:
    async with SessionLocal() as session:
        reran = 0
        if rerun:
            try:
                reader = VillageReader.from_settings()
                reran = await _rerun_certifying_scenarios(session, reader)
            except Exception as exc:  # noqa: BLE001 — degrade to no-rerun sweep
                log.warning("regression_rerun_unavailable", error=str(exc))
        report = await find_and_suspend_regressions(session)
    out = {"reran": reran, **report.as_dict()}
    log.info(
        "regression_sweep",
        reran=reran,
        scanned=report.scanned_certs,
        flips=len(report.flips),
        suspended=len(report.suspended_cert_ids),
    )
    await dispose_engine()
    return out


def run_regression_sweep_job(rerun: bool = True) -> dict:
    """Synchronous entrypoint for the scheduler/RQ."""
    return asyncio.run(_run(rerun))
