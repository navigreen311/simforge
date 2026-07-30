"""Production Outcome Correlation Loop (v1.1).

A certification is a *prediction* that an agent will perform in production. This closes the loop:
record real production outcomes per agent × forge capability and compare them against certification
status. Two miscalibrations matter — a certified agent that underperforms in production (the cert
overstates readiness) and an uncertified agent that performs well (the bar may be too high). Live
production data is an external seam, recorded explicitly here; we never fabricate an outcome score.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cert import AgentCert
from src.models.production_outcome import ProductionOutcome

# A certified agent scoring below this in production is a calibration concern.
UNDERPERFORM_THRESHOLD = 0.70
# An uncertified agent scoring above this may indicate an over-strict bar.
OVERPERFORM_THRESHOLD = 0.85


async def record_outcome(
    session: AsyncSession,
    *,
    agent_village_id: str,
    forge_cap: str,
    outcome_score: float,
    period: str = "",
    sample_size: int = 0,
    source: str = "manual",
    notes: str | None = None,
    recorded_by: str = "system",
) -> ProductionOutcome:
    row = ProductionOutcome(
        agentVillageId=agent_village_id,
        forgeCap=forge_cap,
        outcomeScore=outcome_score,
        period=period,
        sampleSize=sample_size,
        source=source,
        notes=notes,
        recordedBy=recorded_by,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def _latest_outcomes(session: AsyncSession) -> dict[tuple[str, str], ProductionOutcome]:
    rows = (
        (await session.execute(select(ProductionOutcome).order_by(ProductionOutcome.recordedAt)))
        .scalars()
        .all()
    )
    # Keep the most recent per (agent, cap) — later rows overwrite earlier.
    latest: dict[tuple[str, str], ProductionOutcome] = {}
    for r in rows:
        latest[(r.agentVillageId, r.forgeCap)] = r
    return latest


async def correlate(session: AsyncSession) -> dict:
    latest = await _latest_outcomes(session)
    if not latest:
        return {"measured_pairs": 0, "findings": [], "summary": {}}

    # Which (agent, cap) pairs have an active cert.
    agents = {
        a.id: a.villageAgentId for a in (await session.execute(select(Agent))).scalars().all()
    }
    active_certs: set[tuple[str, str]] = set()
    for c in (await session.execute(select(AgentCert))).scalars().all():
        if c.status == "active":
            vid = agents.get(c.agentId)
            if vid:
                active_certs.add((vid, c.forgeCap))

    findings: list[dict] = []
    aligned = 0
    for (vid, cap), outcome in sorted(latest.items()):
        certified = (vid, cap) in active_certs
        score = outcome.outcomeScore
        if certified and score < UNDERPERFORM_THRESHOLD:
            findings.append(
                {
                    "agent": vid,
                    "forge_cap": cap,
                    "kind": "cert_overstates_readiness",
                    "outcome_score": score,
                    "detail": (
                        f"{vid} is certified for {cap} but scored {score:.2f} in production "
                        f"(< {UNDERPERFORM_THRESHOLD}). Consider recertification or scenario fix."
                    ),
                }
            )
        elif not certified and score >= OVERPERFORM_THRESHOLD:
            findings.append(
                {
                    "agent": vid,
                    "forge_cap": cap,
                    "kind": "under_certified",
                    "outcome_score": score,
                    "detail": (
                        f"{vid} is NOT certified for {cap} yet scored {score:.2f} in production. "
                        "The certification bar may be too strict, or a cert is overdue."
                    ),
                }
            )
        else:
            aligned += 1

    return {
        "measured_pairs": len(latest),
        "findings": findings,
        "summary": {
            "aligned": aligned,
            "miscalibrated": len(findings),
            "cert_overstates": sum(1 for f in findings if f["kind"] == "cert_overstates_readiness"),
            "under_certified": sum(1 for f in findings if f["kind"] == "under_certified"),
        },
    }
