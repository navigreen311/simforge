"""Adversarial router — red-team probing of agents (ADR-0028)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.adversarial_probe import AdversarialProbe
from src.services.adversarial import TACTICS, run_adversarial_suite

router = APIRouter()


@router.get("/tactics", dependencies=[Depends(require_role("viewer"))])
async def tactics() -> dict:
    """The red-team tactic catalog (data-driven) — each a pressure toward a compliance violation.

    Detection is SUBSTRING match on the agent's reply (deterministic but brittle)."""
    return {
        "detection": "substring",
        "tactics": [
            {
                "id": t.id,
                "category": t.category,
                "name": t.name,
                "description": t.description,
                "injection": t.injection,
                "targets": list(t.targets),
            }
            for t in TACTICS
        ],
    }


@router.get("/history", dependencies=[Depends(require_role("viewer"))])
async def probe_history(
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Recent probe runs (newest first) so resistance over time is visible. Advisory history."""
    rows = (
        (
            await session.execute(
                select(AdversarialProbe).order_by(AdversarialProbe.createdAt.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return {
        "probes": [
            {
                "id": r.id,
                "scenario_id": r.scenarioId,
                "scenario_title": r.scenarioTitle,
                "agent": r.agent,
                "provider": r.provider,
                "verdict": r.verdict,
                "probes_run": r.probesRun,
                "resisted": r.resisted,
                "capitulated": r.capitulated,
                "resistance_rate": r.resistanceRate,
                "ran_at": r.createdAt.isoformat() if r.createdAt else None,
                "results": r.results,
            }
            for r in rows
        ]
    }


@router.post(
    "/probe/scenario/{scenario_id}",
    dependencies=[Depends(require_role("compliance_analyst"))],
)
async def probe_scenario(
    scenario_id: str,
    agent_id: str | None = Query(
        default=None, description="Probe this agent instead of the bound one"
    ),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Run the full adversarial suite against an agent (the scenario's bound agent, or `agent_id`).

    Persists the run to advisory history. Never blocks or revokes certification."""
    try:
        report = await run_adversarial_suite(session, scenario_id, agent_village_id=agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    session.add(
        AdversarialProbe(
            scenarioId=report["scenario_id"],
            scenarioTitle=report.get("scenario_title", ""),
            agent=report["agent"],
            provider=report["provider"],
            verdict=report["verdict"],
            probesRun=report["probes_run"],
            resisted=report["resisted"],
            capitulated=report["capitulated"],
            resistanceRate=report["resistance_rate"],
            results=report["results"],
        )
    )
    await session.commit()
    return report
