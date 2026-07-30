"""Golden Benchmark router — the evaluator regression suite (ADR-0033)."""

from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import get_village_reader, require_role
from src.models.golden_nomination import GoldenNomination
from src.models.golden_run import GoldenRun
from src.models.pack import Scenario
from src.services.golden import load_baseline, run_golden_suite
from src.services.golden.governance import (
    GoldenGovernanceError,
    list_nominations,
    nominate,
    review,
    withdraw,
)
from src.services.village.reader import VillageReader

router = APIRouter()


class NominateBody(BaseModel):
    scenario_id: str
    nominated_by: str
    rationale: str = ""
    inter_rater_reliability: float | None = None
    council: list[str] | None = None
    quorum_rule: str = "two_of_three"


class ReviewBody(BaseModel):
    approver: str
    decision: str  # approve | reject | abstain
    reason: str = ""


class WithdrawBody(BaseModel):
    actor: str


def _nom_out(n: GoldenNomination) -> dict:
    return {
        "id": n.id,
        "scenario_id": n.scenarioId,
        "nominated_by": n.nominatedBy,
        "rationale": n.rationale,
        "inter_rater_reliability": n.interRaterReliability,
        "approval_request_id": n.approvalRequestId,
        "status": n.status,
        "frozen_at": n.frozenAt.isoformat() if n.frozenAt else None,
        "frozen_by": n.frozenBy,
        "created_at": n.createdAt.isoformat() if n.createdAt else None,
    }


@router.get("/scenarios", dependencies=[Depends(require_role("viewer"))])
async def golden_scenarios(session: AsyncSession = Depends(get_session)) -> dict:
    """The scenarios in the golden set (Scenario.isGolden)."""
    rows = (
        (await session.execute(select(Scenario).where(Scenario.isGolden.is_(True)))).scalars().all()
    )
    return {
        "scenarios": [
            {"scenario_id": s.scenarioId, "title": s.title, "tier": s.tier} for s in rows
        ],
        "total": len(rows),
    }


@router.get("/baseline", dependencies=[Depends(require_role("viewer"))])
async def golden_baseline(session: AsyncSession = Depends(get_session)) -> dict:
    """The committed expected baseline + provenance (who/when/provider), a derived hash, and a
    title per baseline scenario.

    The hash is computed from the scenario baseline only (canonical JSON) so it is a stable
    fingerprint of the reference values these runs are checked against. Titles are resolved for the
    baseline's own scenario ids (not the current golden set) so they read regardless of drift.
    Read-only."""
    baseline = load_baseline()
    scenarios = baseline.get("scenarios", {})
    digest = hashlib.sha256(
        json.dumps(scenarios, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    rows = (
        (await session.execute(select(Scenario).where(Scenario.scenarioId.in_(scenarios.keys()))))
        .scalars()
        .all()
        if scenarios
        else []
    )
    titles = {s.scenarioId: s.title for s in rows}
    return {**baseline, "hash": digest, "titles": titles}


@router.get("/run-history", dependencies=[Depends(require_role("viewer"))])
async def golden_run_history(
    limit: int = Query(default=5, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Recent golden-suite runs (newest first) so stability over time is visible."""
    rows = (
        (await session.execute(select(GoldenRun).order_by(GoldenRun.createdAt.desc()).limit(limit)))
        .scalars()
        .all()
    )
    return {
        "runs": [
            {
                "id": r.id,
                "passed": r.passed,
                "total": r.total,
                "matched": r.matched,
                "regressions": r.regressions,
                "ran_at": r.createdAt.isoformat() if r.createdAt else None,
                "ran_by": r.ranBy,
                "results": r.results,
            }
            for r in rows
        ]
    }


@router.post("/run", dependencies=[Depends(require_role("compliance_analyst"))])
async def run_golden(
    session: AsyncSession = Depends(get_session),
    reader: VillageReader = Depends(get_village_reader),
) -> dict:
    """Run the golden suite and compare against the baseline → a regression report (persisted)."""
    report = await run_golden_suite(session, reader)
    session.add(
        GoldenRun(
            passed=bool(report["passed"]),
            total=report["total"],
            matched=report["matched"],
            regressions=report["regressions"],
            results=report["results"],
        )
    )
    await session.commit()
    return report


# --- §12.5 Golden Benchmark Bank governance: nomination + council review + freeze ---


@router.get("/nominations", dependencies=[Depends(require_role("viewer"))])
async def golden_nominations(
    status_filter: str | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    noms = await list_nominations(session, status=status_filter)
    return {"nominations": [_nom_out(n) for n in noms], "total": len(noms)}


@router.post("/nominations", dependencies=[Depends(require_role("compliance_analyst"))])
async def create_nomination(
    body: NominateBody, session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        nom = await nominate(
            session,
            scenario_id=body.scenario_id,
            nominated_by=body.nominated_by,
            rationale=body.rationale,
            inter_rater_reliability=body.inter_rater_reliability,
            council=body.council,
            quorum_rule=body.quorum_rule,
        )
    except GoldenGovernanceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _nom_out(nom)


@router.post("/nominations/{nomination_id}/review", dependencies=[Depends(require_role("admin"))])
async def review_nomination(
    nomination_id: str, body: ReviewBody, session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        nom = await review(
            session,
            nomination_id=nomination_id,
            approver=body.approver,
            decision=body.decision,
            reason=body.reason,
        )
    except GoldenGovernanceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _nom_out(nom)


@router.post(
    "/nominations/{nomination_id}/withdraw",
    dependencies=[Depends(require_role("compliance_analyst"))],
)
async def withdraw_nomination(
    nomination_id: str, body: WithdrawBody, session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        nom = await withdraw(session, nomination_id=nomination_id, actor=body.actor)
    except GoldenGovernanceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _nom_out(nom)
