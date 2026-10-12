"""ADR-0158: no certificate from practice runs, and the nine issued from them are voided.

- Issuance and reinstatement from a `Run` battery are refused, at the service and the route.
- `revoke_agent_cert(skip_demotion=True)` revokes without the one-level demotion.
- An OperationCertification revocation is recorded, append-only.
- The nightly regression re-run is paused.
- The void: plan reads only; apply revokes the nine and sets the agent's level once, to L1.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cert import AgentCert, AutonomyEvent, CertLifecycleEvent, CertSnapshot
from src.models.operation_cert import OperationCertification, OperationCertificationEvent
from src.services.cert import practice_void
from src.services.cert.registry import (
    PRACTICE_BATTERY_REFUSED,
    CertIssuanceError,
    issue_agent_cert,
    reinstate_agent_cert,
    revoke_agent_cert,
)
from src.services.operation.void import revoke_operation_certification
from src.utils.time import utcnow
from tests.integration.scheduler_path import fresh_session

# --- refusal --------------------------------------------------------------------------------------


async def test_the_service_refuses_issuance_before_any_lookup(db_session: AsyncSession) -> None:
    """Refused for an agent that does not exist and a battery that is empty: nothing is read."""
    with pytest.raises(CertIssuanceError, match="practice run"):
        await issue_agent_cert(
            db_session,
            agent_village_id="nobody",
            forge_cap="x.y.z",
            tier="foundational",
            battery_run_ids=[],
            approver_id="ivan",
            pack_id="none",
        )


async def test_the_service_refuses_reinstatement(db_session: AsyncSession) -> None:
    with pytest.raises(CertIssuanceError, match="practice run"):
        await reinstate_agent_cert(db_session, "no-such-cert", [], "ivan")


async def test_the_issue_route_refuses_and_writes_nothing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.post(
        "/api/certs/agent/issue",
        json={
            "agent_village_id": "david_kim",
            "forge_cap": "cre-forge.deals.title",
            "tier": "foundational",
            "battery_run_ids": ["any-run"],
            "approver_id": "ivan",
            "pack_id": "pack.greenstone.v1",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == PRACTICE_BATTERY_REFUSED
    assert (await db_session.execute(select(AgentCert))).scalars().all() == []


async def test_the_reinstate_route_refuses(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/certs/agent/any-cert/reinstate",
        json={"battery_run_ids": ["any-run"], "approver_id": "ivan"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == PRACTICE_BATTERY_REFUSED


# --- revoke without stacking demotions ------------------------------------------------------------


async def _david(session: AsyncSession, level: str) -> Agent:
    agent = (
        await session.execute(select(Agent).where(Agent.villageAgentId == "david_kim"))
    ).scalar_one()
    agent.currentAutonomyLevel = level
    await session.commit()
    return agent


async def _agent_cert(
    session: AsyncSession, agent: Agent, cert_id: str, cap: str, status: str
) -> AgentCert:
    now = utcnow()
    snap = CertSnapshot(
        snapshotId=f"certsnap:{cert_id}",
        certType="agent_forge_cap",
        subject=agent.villageAgentId,
        forgeCap=cap,
        tier="foundational",
        issuedAt=now,
        expiresAt=now + timedelta(days=90),
        pinnedVersions={"agent_model": "stub-llm"},
        evidenceBundleRef="e",
        signingKeyId="k",
        signature="s",
        contentHash="c",
    )
    session.add(snap)
    await session.flush()
    cert = AgentCert(
        id=cert_id,
        agentId=agent.id,
        forgeCap=cap,
        tier="foundational",
        status=status,
        issuedAt=now,
        expiresAt=now + timedelta(days=90),
        certSnapshotId=snap.id,
    )
    session.add(cert)
    await session.flush()
    return cert


async def test_revoke_without_demotion_keeps_the_level(db_session: AsyncSession) -> None:
    agent = await _david(db_session, "L4")
    cert = await _agent_cert(db_session, agent, "c-nodemote", "cre-forge.demo.a", "active")
    await db_session.commit()

    await revoke_agent_cert(db_session, cert.id, "test", "tester", skip_demotion=True)

    async with fresh_session(db_session) as fresh:
        row = (await fresh.execute(select(AgentCert).where(AgentCert.id == cert.id))).scalar_one()
        assert row.status == "revoked"
        events = (
            (await fresh.execute(select(AutonomyEvent).where(AutonomyEvent.agentId == agent.id)))
            .scalars()
            .all()
        )
        assert events == []
        level = (await fresh.execute(select(Agent).where(Agent.id == agent.id))).scalar_one()
        assert level.currentAutonomyLevel == "L4"


async def test_revoke_still_demotes_by_default(db_session: AsyncSession) -> None:
    agent = await _david(db_session, "L4")
    cert = await _agent_cert(db_session, agent, "c-demote", "cre-forge.demo.b", "active")
    await db_session.commit()

    await revoke_agent_cert(db_session, cert.id, "test", "tester")

    assert agent.currentAutonomyLevel == "L3"


# --- operation certification revocation, append-only --------------------------------------------


def _op_cert(cert_id: str, unit: str = "agent_operation") -> OperationCertification:
    return OperationCertification(
        id=cert_id,
        unitType=unit,
        state="certified",
        forgeId="voiceforge",
        moduleId="call_flow" if unit == "agent_operation" else None,
        agentId="a-op" if unit == "agent_operation" else None,
        departmentId="d-op" if unit == "department_context" else None,
        instructionVersion="2.1.0",
        forgeApiVersion="1.0.0",
        instructionContentHash="sha256:call_flow_v2_1_0",
        operationRubricVersion="0.1.0",
    )


async def test_an_operation_revocation_is_recorded(db_session: AsyncSession) -> None:
    cert = _op_cert("op-1")
    db_session.add(cert)
    await db_session.commit()

    event = await revoke_operation_certification(db_session, cert, reason="why", actor="who")
    await db_session.commit()

    assert event is not None
    async with fresh_session(db_session) as fresh:
        row = (
            await fresh.execute(
                select(OperationCertification).where(OperationCertification.id == "op-1")
            )
        ).scalar_one()
        assert row.state == "revoked"
        ev = (await fresh.execute(select(OperationCertificationEvent))).scalar_one()
        assert (ev.fromState, ev.toState, ev.actor, ev.reason) == (
            "certified",
            "revoked",
            "who",
            "why",
        )


async def test_revoking_twice_records_once(db_session: AsyncSession) -> None:
    cert = _op_cert("op-2")
    db_session.add(cert)
    await db_session.commit()

    await revoke_operation_certification(db_session, cert, reason="why", actor="who")
    again = await revoke_operation_certification(db_session, cert, reason="why", actor="who")
    await db_session.commit()

    assert again is None
    events = (await db_session.execute(select(OperationCertificationEvent))).scalars().all()
    assert len(events) == 1


async def test_a_revocation_needs_a_reason(db_session: AsyncSession) -> None:
    cert = _op_cert("op-3")
    db_session.add(cert)
    await db_session.commit()
    with pytest.raises(ValueError):
        await revoke_operation_certification(db_session, cert, reason=" ", actor="who")
    assert cert.state == "certified"


# --- the paused sweep ----------------------------------------------------------------------------


async def test_the_regression_rerun_is_paused(monkeypatch: pytest.MonkeyPatch) -> None:
    """It returns before opening a session, so nothing is re-run and nothing is read."""
    from src.workers import regression_worker

    def _must_not_open() -> None:
        raise AssertionError("the paused sweep opened a session")

    monkeypatch.setattr(regression_worker, "SessionLocal", _must_not_open)
    out = await regression_worker._run(rerun=True)
    assert out["paused"] is True and out["reran"] == 0
    assert "ADR-0158" in out["reason"]


# --- the void ------------------------------------------------------------------------------------


async def _the_nine(session: AsyncSession, level: str = "L4") -> Agent:
    agent = await _david(session, level)
    for cert_id, cap, status in practice_void.AGENT_CERTS:
        await _agent_cert(session, agent, cert_id, cap, status)
    unit_a, unit_b = (cert_id for cert_id, _, _ in practice_void.OPERATION_CERTS)
    session.add(_op_cert(unit_a))
    session.add(_op_cert(unit_b, unit="department_context"))
    await session.commit()
    return agent


async def test_the_plan_writes_nothing(db_session: AsyncSession) -> None:
    await _the_nine(db_session)

    the_plan = await practice_void.plan(db_session)

    kinds = [s.kind for s in the_plan.steps]
    assert kinds.count("agent_cert") == 7 and kinds.count("operation_cert") == 2
    assert [(s.before, s.after) for s in the_plan.steps if s.kind == "autonomy"] == [("L4", "L1")]
    async with fresh_session(db_session) as fresh:
        statuses = {c.status for c in (await fresh.execute(select(AgentCert))).scalars().all()}
        assert statuses == {"active", "suspended"}
        assert (await fresh.execute(select(CertLifecycleEvent))).scalars().all() == []


async def test_apply_voids_the_nine_and_sets_the_level_once(db_session: AsyncSession) -> None:
    agent = await _the_nine(db_session)

    await practice_void.apply(db_session, actor="Ivan Green")

    async with fresh_session(db_session) as fresh:
        certs = (await fresh.execute(select(AgentCert))).scalars().all()
        assert {c.status for c in certs} == {"revoked"} and len(certs) == 7
        assert all(c.revocationReason == practice_void.REASON for c in certs)
        lifecycle = (await fresh.execute(select(CertLifecycleEvent))).scalars().all()
        assert len(lifecycle) == 7 and {e.event for e in lifecycle} == {"revoked"}
        ops = (await fresh.execute(select(OperationCertification))).scalars().all()
        assert {o.state for o in ops} == {"revoked"}
        assert len((await fresh.execute(select(OperationCertificationEvent))).scalars().all()) == 2
        moves = (
            (await fresh.execute(select(AutonomyEvent).where(AutonomyEvent.agentId == agent.id)))
            .scalars()
            .all()
        )
        assert [(m.fromLevel, m.toLevel) for m in moves] == [("L4", "L1")]
        assert moves[0].reason == practice_void.LEVEL_REASON


async def test_apply_twice_changes_nothing_the_second_time(db_session: AsyncSession) -> None:
    await _the_nine(db_session)
    await practice_void.apply(db_session, actor="Ivan Green")

    second = await practice_void.apply(db_session, actor="Ivan Green")

    assert second.steps == [] and len(second.skipped) == 9
    assert len((await db_session.execute(select(CertLifecycleEvent))).scalars().all()) == 7


async def test_a_moved_target_refuses_the_whole_void(db_session: AsyncSession) -> None:
    await _the_nine(db_session)
    first_id = practice_void.AGENT_CERTS[0][0]
    moved = (
        await db_session.execute(select(AgentCert).where(AgentCert.id == first_id))
    ).scalar_one()
    moved.status = "suspended"  # was active when the ruling was given
    await db_session.commit()

    with pytest.raises(practice_void.VoidRefused, match=first_id):
        await practice_void.apply(db_session, actor="Ivan Green")
    assert (await db_session.execute(select(CertLifecycleEvent))).scalars().all() == []


async def test_a_surviving_certification_refuses_the_floor(db_session: AsyncSession) -> None:
    """L1 is for an agent with no valid certification. If one survives, the void refuses."""
    agent = await _the_nine(db_session)
    await _agent_cert(db_session, agent, "c-survivor", "cre-forge.demo.kept", "active")
    await db_session.commit()

    with pytest.raises(practice_void.VoidRefused, match="c-survivor"):
        await practice_void.plan(db_session)
