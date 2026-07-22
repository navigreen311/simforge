"""Scenarios router (blueprint §C.3.5). Phase 3: list + detail. `run` endpoints land in Phase 4."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import get_village_reader, require_role
from src.models.pack import Pack, Scenario
from src.schemas.pack import ScenarioSummary
from src.schemas.run import RunSummary
from src.services.runner import RunnerError, run_scenario
from src.services.village.reader import VillageReader

router = APIRouter()


@router.get("/", dependencies=[Depends(require_role("viewer"))])
async def list_scenarios(
    session: AsyncSession = Depends(get_session),
    pack_id: str | None = Query(default=None, description="Filter by Pack packId"),
    tier: str | None = Query(default=None),
) -> dict:
    stmt = select(Scenario)
    count_stmt = select(func.count()).select_from(Scenario)
    if pack_id:
        stmt = stmt.join(Pack, Scenario.packId == Pack.id).where(Pack.packId == pack_id)
        count_stmt = count_stmt.join(Pack, Scenario.packId == Pack.id).where(Pack.packId == pack_id)
    if tier:
        stmt = stmt.where(Scenario.tier == tier)
        count_stmt = count_stmt.where(Scenario.tier == tier)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt.order_by(Scenario.scenarioId))).scalars().all()
    return {
        "items": [ScenarioSummary.model_validate(s).model_dump() for s in rows],
        "total": total,
    }


@router.get(
    "/{scenario_id}",
    response_model=ScenarioSummary,
    dependencies=[Depends(require_role("viewer"))],
)
async def get_scenario(
    scenario_id: str, session: AsyncSession = Depends(get_session)
) -> ScenarioSummary:
    scen = (
        await session.execute(select(Scenario).where(Scenario.scenarioId == scenario_id))
    ).scalar_one_or_none()
    if scen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    return ScenarioSummary.model_validate(scen)


@router.post(
    "/{scenario_id}/run",
    response_model=RunSummary,
    dependencies=[Depends(require_role("prompt_engineer"))],
)
async def run_scenario_endpoint(
    scenario_id: str,
    integrated: bool = False,
    narrative_mode: str | None = None,
    session: AsyncSession = Depends(get_session),
    reader: VillageReader = Depends(get_village_reader),
) -> RunSummary:
    """Execute a scenario run and return the result.

    Sandbox by default. `integrated=true` requests write-enabled execution (ADR-0025) — honored only
    when INTEGRATED_EXECUTION_ENABLED is on and the pack allows it; otherwise the run stays sandbox.
    `narrative_mode=integrated` produces Village narrative effects (ADR-0035); default follows the
    pack's `narrativeModeDefault` (`protected`). Narrative effects never write VillageData.
    """
    from src.routers.runs import _summarize
    from src.services.evaluation import evaluate_run
    from src.services.narrative import apply_narrative_effects
    from src.services.reporter import emit_reports
    from src.telemetry.metrics import GATE_PASSED_TOTAL, RUN_DURATION, RUNS_TOTAL

    try:
        run = await run_scenario(
            session, scenario_id, reader, integrated=integrated, narrative_mode=narrative_mode
        )
    except RunnerError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    # Metrics (token counts are emitted per-call by the LLM providers).
    RUNS_TOTAL.labels(status=run.status, execution_mode=run.executionMode).inc()
    if run.latencyMs is not None:
        RUN_DURATION.labels(tier="all").observe(run.latencyMs / 1000.0)

    # Evaluate the completed run (15-dim rubric + gate) then emit the gap reports.
    if run.status != "errored":
        card = await evaluate_run(session, run.id)
        GATE_PASSED_TOTAL.labels(tier="all", passed=str(card.readinessGatePassed).lower()).inc()
        await emit_reports(session, run.id)
        # Integrated-narrative runs also accrete a story-level beat (ADR-0035); protected → no-op.
        await apply_narrative_effects(session, run, card)
    return await _summarize(session, run)
