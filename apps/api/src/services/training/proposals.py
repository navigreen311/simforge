"""Agent training proposals (blueprint §L.4; ADR-0026).

Closes the certifier → improver loop. `analyze_run_for_training` reads a run's scorecard, and if an
LLM-judge dimension (P7/C1/C2 — the ones a prompt can move) is weak, generates a **proposal**: a
candidate prompt refinement + a bumped prompt version. It is never auto-applied. `approve_proposal`
promotes the prompt version and **suspends the agent's certs pinned to the old version** (they must
be re-certified — same mechanism as drift/amendment), so an improvement can't quietly bypass
governance.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cert import AgentCert, CertLifecycleEvent, CertSnapshot
from src.models.run import Run
from src.models.scorecard import Scorecard
from src.models.training import TrainingProposal
from src.services.cert.autonomy_ladder import LEVELS, demote
from src.utils.time import utcnow

# LLM-judge dims a prompt refinement can plausibly improve (weakness threshold + guidance).
_JUDGE_DIMS = {
    "p7_cx": (
        "p7CustomerExperience",
        0.60,
        "Lead with empathy, confirm consent, and pace to the counterparty; avoid curt, "
        "transactional phrasing.",
    ),
    "c1_breath": (
        "c1BreathCoherence",
        0.60,
        "Keep beliefs/ethics/habits consistent across turns; don't contradict earlier commitments.",
    ),
    "c2_soul": (
        "c2SoulStability",
        0.60,
        "Hold a steady emotional register under pressure; acknowledge stress without absorbing it.",
    ),
}


def _bump_version(version: str) -> str:
    m = re.search(r"(\d+)$", version)
    if m:
        return version[: m.start()] + str(int(m.group(1)) + 1)
    return f"{version}.v2"


async def analyze_run_for_training(
    session: AsyncSession, run_id: str, *, current_prompt_version: str = "prompt.v1"
) -> TrainingProposal | None:
    """Generate a training proposal if the run's scorecard has a weak LLM-judge dim; else None."""
    run = (await session.execute(select(Run).where(Run.runId == run_id))).scalar_one_or_none()
    if run is None:
        return None
    card = (
        await session.execute(select(Scorecard).where(Scorecard.runId == run.id))
    ).scalar_one_or_none()
    if card is None:
        return None

    weak: list[str] = []
    guidance: list[str] = []
    for dim, (attr, threshold, tip) in _JUDGE_DIMS.items():
        val = getattr(card, attr, None)
        if val is not None and val < threshold:
            weak.append(dim)
            guidance.append(f"- {dim}: {tip}")
    if not weak:
        return None

    proposal = TrainingProposal(
        agentId=run.agentId,
        runId=run.id,
        weakDims=weak,
        currentPromptVersion=current_prompt_version,
        proposedPromptVersion=_bump_version(current_prompt_version),
        rationale=f"Run {run_id} scored low on {', '.join(weak)}; propose a targeted refinement.",
        proposedRefinement="Prompt addendum:\n" + "\n".join(guidance),
        status="proposed",
        autoApplied=False,
    )
    session.add(proposal)
    await session.commit()
    await session.refresh(proposal)
    return proposal


async def approve_proposal(session: AsyncSession, proposal_id: str, approver: str) -> dict:
    """Approve → promote the prompt version + suspend certs pinned to the old version (re-cert)."""
    proposal = (
        await session.execute(select(TrainingProposal).where(TrainingProposal.id == proposal_id))
    ).scalar_one_or_none()
    if proposal is None:
        raise ValueError(f"Proposal not found: {proposal_id}")
    if proposal.status != "proposed":
        raise ValueError(f"Proposal already {proposal.status}")

    now = utcnow()
    proposal.status = "approved"
    proposal.reviewedBy = approver
    proposal.reviewedAt = now

    # Suspend the agent's active certs pinned to the OLD prompt version — they must be re-certified
    # against the improved prompt (mirrors drift/amendment auto-suspend).
    agent = (
        await session.execute(select(Agent).where(Agent.id == proposal.agentId))
    ).scalar_one_or_none()
    suspended: list[str] = []
    certs = (
        (
            await session.execute(
                select(AgentCert).where(
                    AgentCert.agentId == proposal.agentId, AgentCert.status == "active"
                )
            )
        )
        .scalars()
        .all()
    )
    for cert in certs:
        snap = (
            await session.execute(
                select(CertSnapshot).where(CertSnapshot.id == cert.certSnapshotId)
            )
        ).scalar_one_or_none()
        pinned = snap.pinnedVersions.get("agent_prompt_version") if snap else None
        if pinned == proposal.currentPromptVersion:
            cert.status = "suspended"
            reason = f"agent prompt updated to {proposal.proposedPromptVersion} pending re-cert"
            session.add(
                CertLifecycleEvent(
                    agentCertId=cert.id,
                    event="suspended",
                    timestamp=now,
                    actor=approver,
                    reason=reason,
                    snapshotIdAtEvent=snap.snapshotId if snap else None,
                )
            )
            suspended.append(cert.forgeCap)

    if suspended and agent is not None:
        idx = (
            LEVELS.index(agent.currentAutonomyLevel) if agent.currentAutonomyLevel in LEVELS else 0
        )
        if idx > 0:
            await demote(session, agent, LEVELS[idx - 1], "prompt update pending re-cert", approver)

    await session.commit()

    # Real-time PEP invalidation for each suspended cert (best-effort; §F.4).
    if suspended and agent is not None:
        from src.services.governance.revocation import publish_cert_event

        for cap in suspended:
            await publish_cert_event(agent.villageAgentId, cap, "suspended")

    return {
        "proposal_id": proposal_id,
        "status": "approved",
        "new_prompt_version": proposal.proposedPromptVersion,
        "certs_suspended": suspended,
    }


async def reject_proposal(session: AsyncSession, proposal_id: str, reviewer: str) -> dict:
    proposal = (
        await session.execute(select(TrainingProposal).where(TrainingProposal.id == proposal_id))
    ).scalar_one_or_none()
    if proposal is None:
        raise ValueError(f"Proposal not found: {proposal_id}")
    if proposal.status != "proposed":
        raise ValueError(f"Proposal already {proposal.status}")
    proposal.status = "rejected"
    proposal.reviewedBy = reviewer
    proposal.reviewedAt = utcnow()
    await session.commit()
    return {"proposal_id": proposal_id, "status": "rejected"}
