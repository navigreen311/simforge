"""PDP decision engine — the cert × autonomy × safe-mode decision matrix (ADR-0024)."""

from __future__ import annotations

from datetime import timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cert import AgentCert, CertSnapshot
from src.models.department import Department
from src.services.governance.pdp import AuthRequest, fail_policy_for, pdp
from src.services.governance.safe_mode import safe_mode
from src.utils.time import utcnow

ACTION = "cre-forge.call_center.outbound"


async def _seed_cert(
    session: AsyncSession,
    *,
    autonomy: str,
    status: str = "active",
    expires_in_days: int = 30,
    forge_cap: str = ACTION,
) -> str:
    dept = Department(villageKey="PDP", name="PDP Dept", totalAgents=1)
    session.add(dept)
    await session.flush()
    agent = Agent(
        villageAgentId="pdp_agent",
        name="PDP Agent",
        role="Agent",
        departmentId=dept.id,
        currentAutonomyLevel=autonomy,
    )
    session.add(agent)
    await session.flush()
    snap = CertSnapshot(
        snapshotId="certsnap:pdp",
        certType="agent_forge_cap",
        subject="pdp_agent",
        forgeCap=forge_cap,
        tier="foundational",
        issuedAt=utcnow(),
        expiresAt=utcnow() + timedelta(days=expires_in_days),
        pinnedVersions={},
        evidenceBundleRef="",
        signingKeyId="k",
        signature="s",
        contentHash="h",
    )
    session.add(snap)
    await session.flush()
    cert = AgentCert(
        agentId=agent.id,
        forgeCap=forge_cap,
        tier="foundational",
        status=status,
        issuedAt=utcnow(),
        expiresAt=utcnow() + timedelta(days=expires_in_days),
        certSnapshotId=snap.id,
    )
    session.add(cert)
    await session.commit()
    return agent.villageAgentId


@pytest_asyncio.fixture(autouse=True)
async def _reset_safe_mode():
    safe_mode.deactivate()
    yield
    safe_mode.deactivate()


@pytest.mark.parametrize(
    ("autonomy", "decision", "reason"),
    [
        ("L5", "allow", "autonomy_sufficient"),
        ("L4", "allow", "autonomy_sufficient"),
        ("L3", "step_up_approval_required", "approval_required_l3"),
        ("L2", "downgrade_and_retry", "draft_only_l2"),
        ("L1", "deny", "observe_only_l1"),
    ],
)
async def test_active_cert_maps_autonomy_to_decision(
    db_session: AsyncSession, autonomy: str, decision: str, reason: str
) -> None:
    aid = await _seed_cert(db_session, autonomy=autonomy)
    d = await pdp.decide(db_session, AuthRequest(subject_agent_id=aid, action=ACTION))
    assert d.decision == decision and d.reason_code == reason
    assert d.ttl_seconds > 0 and d.fail_policy == "fail_closed"
    if decision == "step_up_approval_required":
        assert d.required_approver == "human_supervisor"


@pytest.mark.parametrize(
    ("cert_status", "reason"),
    [("suspended", "cert_suspended"), ("revoked", "cert_revoked")],
)
async def test_non_active_cert_denies(
    db_session: AsyncSession, cert_status: str, reason: str
) -> None:
    aid = await _seed_cert(db_session, autonomy="L5", status=cert_status)
    d = await pdp.decide(db_session, AuthRequest(subject_agent_id=aid, action=ACTION))
    assert d.decision == "deny" and d.reason_code == reason


async def test_expired_cert_denies(db_session: AsyncSession) -> None:
    aid = await _seed_cert(db_session, autonomy="L5", expires_in_days=-1)
    d = await pdp.decide(db_session, AuthRequest(subject_agent_id=aid, action=ACTION))
    assert d.decision == "deny" and d.reason_code == "cert_expired"


async def test_no_cert_and_unknown_agent_deny(db_session: AsyncSession) -> None:
    aid = await _seed_cert(db_session, autonomy="L5")
    # Known agent, action it isn't certified for.
    d1 = await pdp.decide(db_session, AuthRequest(subject_agent_id=aid, action="vaf.doc.retrieve"))
    assert d1.decision == "deny" and d1.reason_code == "no_certification"
    # Unknown agent entirely.
    d2 = await pdp.decide(db_session, AuthRequest(subject_agent_id="ghost", action=ACTION))
    assert d2.decision == "deny" and d2.reason_code == "unknown_subject"


async def test_safe_mode_forces_step_up(db_session: AsyncSession) -> None:
    aid = await _seed_cert(db_session, autonomy="L5")  # would otherwise allow
    safe_mode.activate("admin", "incident", None)
    d = await pdp.decide(db_session, AuthRequest(subject_agent_id=aid, action=ACTION))
    assert d.decision == "step_up_approval_required" and d.reason_code == "safe_mode_active"


def test_fail_policy_default_closed() -> None:
    assert fail_policy_for("cre-forge.call_center.outbound") == "fail_closed"
    assert fail_policy_for("medlink-pro.scheduler.shift_fill") == "fail_closed"
