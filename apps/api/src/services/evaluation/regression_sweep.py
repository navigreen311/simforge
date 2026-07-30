"""Regression sweep — detect verified scenario flips and auto-suspend the affected cert (§9.2,
§11.3 trigger #2).

Two layers:
  - `find_and_suspend_regressions` (pure DB): for each active AgentCert, compare the agent's two
    most-recent runs on each scenario whose tested caps include the cert's cap. A prior-passing /
    now-failing flip is a regression → the cert is auto-suspended (lifecycle event + one-level
    autonomy demote + best-effort PEP invalidation). Hermetic — no re-execution, no LLM, no reader.
  - `run_regression_sweep` (nightly worker core): re-runs each active cert's certifying scenarios
    first (fresh evidence), then calls the pure layer. Needs a VillageReader + provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cert import AgentCert, CertLifecycleEvent
from src.models.pack import Scenario
from src.models.run import Run
from src.models.scorecard import Scorecard
from src.services.cert.autonomy_ladder import LEVELS, demote
from src.utils.time import utcnow


@dataclass
class RegressionFlip:
    cert_id: str
    agent_village_id: str
    forge_cap: str
    scenario_id: str
    detail: str


@dataclass
class RegressionSweepReport:
    scanned_certs: int
    flips: list[RegressionFlip] = field(default_factory=list)
    suspended_cert_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "scanned_certs": self.scanned_certs,
            "flips": [f.__dict__ for f in self.flips],
            "suspended_cert_ids": self.suspended_cert_ids,
        }


async def _latest_two_runs(session: AsyncSession, agent_id: str, scenario_pk: str) -> list[Run]:
    return list(
        (
            await session.execute(
                select(Run)
                .where(Run.agentId == agent_id, Run.scenarioId == scenario_pk)
                .order_by(Run.startedAt.desc())
                .limit(2)
            )
        )
        .scalars()
        .all()
    )


async def _passed(session: AsyncSession, run: Run) -> bool | None:
    card = (
        await session.execute(select(Scorecard).where(Scorecard.runId == run.id))
    ).scalar_one_or_none()
    return None if card is None else bool(card.readinessGatePassed)


async def find_and_suspend_regressions(
    session: AsyncSession, *, suspend: bool = True, actor: str = "regression-sweep"
) -> RegressionSweepReport:
    """Detect prior-pass/now-fail flips on scenarios covering a cert's cap; suspend on flip."""
    certs = (
        (await session.execute(select(AgentCert).where(AgentCert.status == "active")))
        .scalars()
        .all()
    )
    scenarios = (await session.execute(select(Scenario))).scalars().all()
    agents = {a.id: a for a in (await session.execute(select(Agent))).scalars().all()}

    report = RegressionSweepReport(scanned_certs=len(certs))
    now = utcnow()

    for cert in certs:
        covering = [s for s in scenarios if cert.forgeCap in (s.testedForgeCaps or [])]
        flip: RegressionFlip | None = None
        for scenario in covering:
            runs = await _latest_two_runs(session, cert.agentId, scenario.id)
            if len(runs) < 2:
                continue
            current_pass = await _passed(session, runs[0])
            prior_pass = await _passed(session, runs[1])
            if prior_pass and current_pass is False:
                agent = agents.get(cert.agentId)
                flip = RegressionFlip(
                    cert_id=cert.id,
                    agent_village_id=agent.villageAgentId if agent else cert.agentId,
                    forge_cap=cert.forgeCap,
                    scenario_id=scenario.scenarioId,
                    detail=f"prior_passed=True current_passed=False on {scenario.scenarioId}",
                )
                break
        if flip is None:
            continue
        report.flips.append(flip)
        if not suspend:
            continue

        cert.status = "suspended"
        session.add(
            CertLifecycleEvent(
                agentCertId=cert.id,
                event="suspended",
                timestamp=now,
                actor=actor,
                reason=f"regression: {flip.detail}",
            )
        )
        agent = agents.get(cert.agentId)
        if agent is not None:
            idx = (
                LEVELS.index(agent.currentAutonomyLevel)
                if agent.currentAutonomyLevel in LEVELS
                else 0
            )
            if idx > 0:
                await demote(
                    session, agent, LEVELS[idx - 1], f"regression: {flip.scenario_id}", actor
                )
        report.suspended_cert_ids.append(cert.id)

    if suspend and report.suspended_cert_ids:
        await session.commit()
        from src.services.governance.revocation import publish_cert_event

        for flip in report.flips:
            if flip.cert_id in report.suspended_cert_ids:
                await publish_cert_event(flip.agent_village_id, flip.forge_cap, "suspended")
    return report
