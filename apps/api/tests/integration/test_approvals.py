"""Approval Workflow Engine (§11.5): quorum modes, signed journal, TTL expiry, double-vote guard."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.approval import ApprovalRequest
from src.utils.time import utcnow


async def _create(client: AsyncClient, **over) -> dict:
    body = {
        "kind": "autonomy_transition",
        "subject": {"agent": "david_kim", "to": "L4"},
        "summary": "Promote david_kim to L4",
        "quorum_rule": "single",
        "required_approvers": [],
    }
    body.update(over)
    resp = await client.post("/api/approvals/", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_single_quorum_approve_resolves(client: AsyncClient) -> None:
    req = await _create(client)
    assert req["status"] == "pending"
    out = (
        await client.post(
            f"/api/approvals/{req['id']}/vote",
            json={"approver": "ivan", "decision": "approve", "reason": "clean streak"},
        )
    ).json()
    assert out["request"]["status"] == "approved" and out["request"]["resolution"] == "approved"
    # Signed journal recorded the vote + reason.
    assert out["journal"][0]["approver"] == "ivan"
    assert out["journal"][0]["reason"] == "clean streak"


async def test_two_of_three_needs_two_approvals(client: AsyncClient) -> None:
    req = await _create(client, quorum_rule="two_of_three")
    one = (
        await client.post(
            f"/api/approvals/{req['id']}/vote", json={"approver": "a", "decision": "approve"}
        )
    ).json()
    assert one["request"]["status"] == "pending"  # 1 of 2 not enough
    two = (
        await client.post(
            f"/api/approvals/{req['id']}/vote", json={"approver": "b", "decision": "approve"}
        )
    ).json()
    assert two["request"]["status"] == "approved"


async def test_unanimous_requires_all_named_approvers(client: AsyncClient) -> None:
    req = await _create(
        client,
        kind="constitutional_amendment",
        quorum_rule="unanimous",
        required_approvers=["ivan", "witness"],
    )
    a = (
        await client.post(
            f"/api/approvals/{req['id']}/vote", json={"approver": "ivan", "decision": "approve"}
        )
    ).json()
    assert a["request"]["status"] == "pending"  # not all named approvers yet
    b = (
        await client.post(
            f"/api/approvals/{req['id']}/vote", json={"approver": "witness", "decision": "approve"}
        )
    ).json()
    assert b["request"]["status"] == "approved"


async def test_reject_resolves_and_double_vote_blocked(client: AsyncClient) -> None:
    req = await _create(client, quorum_rule="two_of_three")
    await client.post(
        f"/api/approvals/{req['id']}/vote", json={"approver": "a", "decision": "approve"}
    )
    # Same approver voting twice is rejected.
    dup = await client.post(
        f"/api/approvals/{req['id']}/vote", json={"approver": "a", "decision": "approve"}
    )
    assert dup.status_code == 400 and "already voted" in dup.json()["detail"].lower()


async def test_unanimous_requires_named_approvers_at_create(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/approvals/",
        json={"kind": "constitutional_amendment", "quorum_rule": "unanimous", "subject": {}},
    )
    assert resp.status_code == 400 and "unanimous" in resp.json()["detail"].lower()


async def test_expired_request_cannot_be_voted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    req = await _create(client)
    # Force the TTL into the past.
    row = (
        await db_session.execute(select(ApprovalRequest).where(ApprovalRequest.id == req["id"]))
    ).scalar_one()
    from datetime import timedelta

    row.expiresAt = utcnow() - timedelta(hours=1)
    await db_session.commit()

    # The escalation sweep marks it expired.
    swept = (await client.post("/api/approvals/expire-stale")).json()
    assert req["id"] in swept["expired"]
    # And a vote now fails.
    late = await client.post(
        f"/api/approvals/{req['id']}/vote", json={"approver": "ivan", "decision": "approve"}
    )
    assert late.status_code == 400


async def test_bad_kind_rejected(client: AsyncClient) -> None:
    resp = await client.post("/api/approvals/", json={"kind": "nonsense", "subject": {}})
    assert resp.status_code == 400 and "kind" in resp.json()["detail"].lower()


async def test_escalation_job_runs_on_demand(client: AsyncClient) -> None:
    result = (await client.post("/api/scheduler/run/hourly_approval_escalation")).json()
    assert result["job"] == "hourly_approval_escalation" and "count" in result


@pytest.mark.parametrize("kind", ["cert_issuance", "rubric_amendment", "policy_change"])
async def test_valid_kinds_accepted(client: AsyncClient, kind: str) -> None:
    req = await _create(client, kind=kind)
    assert req["kind"] == kind
