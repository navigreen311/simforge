"""Linear INBOUND webhook (§C.11): issue state changes close the gap loop."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.gap import SoftwareGap, VillageOSGap


def _seed_software_gap(session: AsyncSession, *, linear_id: str, status: str = "open") -> None:
    session.add(
        SoftwareGap(
            ticketId=f"SF-GAP-{linear_id}",
            runId="run-x",
            forge="capital-forge",
            module="ledger",
            severity="P1",
            summary="reconciliation drift",
            detail="…",
            linearId=linear_id,
            status=status,
            firstSeenRunId="run-x",
            lastSeenRunId="run-x",
        )
    )


def _issue_event(issue_id: str, state_type: str) -> dict:
    return {
        "action": "update",
        "type": "Issue",
        "data": {"id": issue_id, "identifier": "SF-1", "state": {"name": "X", "type": state_type}},
    }


async def test_completed_issue_resolves_gap(client: AsyncClient, db_session: AsyncSession) -> None:
    _seed_software_gap(db_session, linear_id="lin-1")
    await db_session.commit()

    res = await client.post("/api/webhooks/linear", json=_issue_event("lin-1", "completed"))
    body = res.json()
    assert res.status_code == 200
    assert body["handled"] is True and body["changed"] is True
    assert body["new_status"] == "resolved"

    gap = (
        await db_session.execute(select(SoftwareGap).where(SoftwareGap.linearId == "lin-1"))
    ).scalar_one()
    assert gap.status == "resolved"


async def test_canceled_issue_marks_wontfix(client: AsyncClient, db_session: AsyncSession) -> None:
    _seed_software_gap(db_session, linear_id="lin-2")
    await db_session.commit()
    res = await client.post("/api/webhooks/linear", json=_issue_event("lin-2", "canceled"))
    assert res.json()["new_status"] == "wontfix"


async def test_village_os_gap_synced(client: AsyncClient, db_session: AsyncSession) -> None:
    db_session.add(
        VillageOSGap(
            ticketId="SF-VG-1",
            runId="run-x",
            framework="soul",
            severity="P2",
            summary="identity drift",
            detail="…",
            linearId="lin-vg",
            status="open",
        )
    )
    await db_session.commit()
    res = await client.post("/api/webhooks/linear", json=_issue_event("lin-vg", "completed"))
    body = res.json()
    assert body["kind"] == "village_os"
    assert body["new_status"] == "resolved"


async def test_unknown_issue_is_noop(client: AsyncClient) -> None:
    res = await client.post("/api/webhooks/linear", json=_issue_event("nope", "completed"))
    assert res.status_code == 200
    assert res.json()["handled"] is False


async def test_non_issue_type_ignored(client: AsyncClient) -> None:
    res = await client.post("/api/webhooks/linear", json={"type": "Comment", "data": {"id": "c1"}})
    assert res.json()["handled"] is False


async def test_signature_enforced_when_secret_set(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_software_gap(db_session, linear_id="lin-sig")
    await db_session.commit()
    monkeypatch.setattr(settings, "linear_webhook_secret", "s3cr3t")
    payload = _issue_event("lin-sig", "completed")
    raw = json.dumps(payload).encode()

    # Missing/incorrect signature is rejected.
    bad = await client.post(
        "/api/webhooks/linear", content=raw, headers={"Content-Type": "application/json"}
    )
    assert bad.status_code == 401

    # Correct HMAC is accepted.
    sig = hmac.new(b"s3cr3t", raw, hashlib.sha256).hexdigest()
    good = await client.post(
        "/api/webhooks/linear",
        content=raw,
        headers={"Content-Type": "application/json", "Linear-Signature": sig},
    )
    assert good.status_code == 200
    assert good.json()["new_status"] == "resolved"
