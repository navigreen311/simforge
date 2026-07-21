"""Emit the triple report for a run: detect + persist Software and Village-OS gaps.

The Agent Scorecard (report #1) is produced by the evaluation engine (Phase 5). This module
adds reports #2 (Software Gaps) and #3 (Village-OS Gaps), dedup-persisted and routed to
Linear (a no-op in dev).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ccb import CCB as CCBModel
from src.models.gap import SoftwareGap, VillageOSGap
from src.models.pack import Scenario
from src.models.run import Run, TraceEvent
from src.models.scorecard import Scorecard
from src.services.reporter.linear_client import LinearClient
from src.services.reporter.software_gap import (
    detect_forge_fault_gaps,
    detect_software_gaps,
    ticket_id,
)
from src.services.reporter.village_os_gap import detect_village_os_gaps

_FRAMEWORKS = ("game", "mate", "soul", "breath", "fot", "hfm", "arc", "echo", "drift", "ame")


@dataclass
class ReportResult:
    software_gaps: int
    village_os_gaps: int


async def _ccb_frameworks(session: AsyncSession, ccb_id: str | None) -> dict | None:
    if ccb_id is None:
        return None
    row = (
        await session.execute(select(CCBModel).where(CCBModel.id == ccb_id))
    ).scalar_one_or_none()
    return {fw: getattr(row, fw) for fw in _FRAMEWORKS} if row else None


async def emit_reports(session: AsyncSession, run_internal_id: str) -> ReportResult:
    run = (await session.execute(select(Run).where(Run.id == run_internal_id))).scalar_one()
    scenario = (
        await session.execute(select(Scenario).where(Scenario.id == run.scenarioId))
    ).scalar_one()
    scorecard = (
        await session.execute(select(Scorecard).where(Scorecard.runId == run.id))
    ).scalar_one_or_none()
    ccb_post = await _ccb_frameworks(session, run.ccbPostId)
    linear = LinearClient()

    # --- Software gaps (heuristic + real Forge faults from trace events) ---
    fault_events = (
        (
            await session.execute(
                select(TraceEvent.payload).where(
                    TraceEvent.runId == run.id, TraceEvent.eventType == "forge_fault"
                )
            )
        )
        .scalars()
        .all()
    )
    candidates = detect_software_gaps(run, scenario) + detect_forge_fault_gaps(list(fault_events))
    sw_count = 0
    for cand in candidates:
        tid = ticket_id("SF-GAP", f"{cand.forge}:{cand.module}:{cand.severity}:{cand.summary}")
        existing = (
            await session.execute(select(SoftwareGap).where(SoftwareGap.ticketId == tid))
        ).scalar_one_or_none()
        if existing:
            existing.occurrenceCount += 1
            existing.lastSeenRunId = run.runId
        else:
            ticket = await linear.create_ticket(
                project=f"{cand.forge}-gaps",
                title=f"[{cand.severity}] {cand.summary}",
                description=cand.detail,
                metadata={"simforge_ticket_id": tid, "run_id": run.runId},
            )
            session.add(
                SoftwareGap(
                    ticketId=tid,
                    runId=run.id,
                    forge=cand.forge,
                    module=cand.module,
                    severity=cand.severity,
                    summary=cand.summary,
                    detail=cand.detail,
                    proposedFix=cand.proposed_fix,
                    linearId=ticket.linear_id,
                    linearUrl=ticket.linear_url,
                    firstSeenRunId=run.runId,
                    lastSeenRunId=run.runId,
                )
            )
            sw_count += 1

    # --- Village-OS gaps ---
    vos_count = 0
    arc = scorecard.c4ArcNarrativeCoherence if scorecard else None
    for cand in detect_village_os_gaps(arc, ccb_post):
        tid = ticket_id("SF-VG", f"{cand.framework}:{cand.severity}:{cand.summary}")
        existing = (
            await session.execute(select(VillageOSGap).where(VillageOSGap.ticketId == tid))
        ).scalar_one_or_none()
        if existing:
            existing.occurrenceCount += 1
        else:
            ticket = await linear.create_ticket(
                project="village-os-gaps",
                title=f"[{cand.severity}] {cand.framework}: {cand.summary}",
                description=cand.detail,
                metadata={"simforge_ticket_id": tid, "run_id": run.runId},
            )
            session.add(
                VillageOSGap(
                    ticketId=tid,
                    runId=run.id,
                    framework=cand.framework,
                    severity=cand.severity,
                    summary=cand.summary,
                    detail=cand.detail,
                    proposedFix=cand.proposed_fix,
                    linearId=ticket.linear_id,
                    linearUrl=ticket.linear_url,
                )
            )
            vos_count += 1

    await session.commit()
    return ReportResult(software_gaps=sw_count, village_os_gaps=vos_count)
