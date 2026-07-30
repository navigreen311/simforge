"""Waiver/exception registry + Appeal workflow (§11.5)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.waiver import Appeal, Waiver
from src.services.governance.waiver import expire_waivers
from src.utils.time import utcnow

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")
FORGE_CAP = "cre-forge.call_center.outbound_seller_outreach"


async def test_waiver_grant_list_revoke(client: AsyncClient) -> None:
    w = (
        await client.post(
            "/api/waivers/",
            json={
                "subject": "david_kim",
                "scope": "autonomy:L4",
                "reason": "shift backfill",
                "ttl_hours": 6,
                "compensating_controls": ["hourly spot-check"],
            },
        )
    ).json()
    assert w["status"] == "active" and w["scope"] == "autonomy:L4"
    listed = (await client.get("/api/waivers/")).json()["waivers"]
    assert any(x["id"] == w["id"] for x in listed)
    revoked = (await client.post(f"/api/waivers/{w['id']}/revoke")).json()
    assert revoked["status"] == "revoked"


async def test_waiver_rejects_nonpositive_ttl(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/waivers/",
        json={"subject": "x", "scope": "y", "ttl_hours": 0},
    )
    assert resp.status_code == 400


async def test_expire_waivers_sweep(client: AsyncClient, db_session: AsyncSession) -> None:
    await client.post(
        "/api/waivers/",
        json={"subject": "a", "scope": "s", "ttl_hours": 1},
    )
    w = (await db_session.execute(select(Waiver))).scalars().first()
    w.expiresAt = utcnow() - timedelta(hours=2)
    await db_session.commit()
    expired = await expire_waivers(db_session)
    assert w.id in expired
    assert (await db_session.execute(select(Waiver))).scalars().first().status == "expired"


async def _issue_and_revoke_cert(client: AsyncClient) -> str:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    run = (await client.post("/api/scenarios/scn.gs.src.001/run")).json()
    issue = await client.post(
        "/api/certs/agent/issue",
        json={
            "agent_village_id": "david_kim",
            "forge_cap": FORGE_CAP,
            "tier": "foundational",
            "battery_run_ids": [run["run_id"]],
            "approver_id": "ivan",
            "pack_id": "pack.greenstone.v1",
        },
    )
    cert_id = issue.json()["cert"]["id"]
    await client.post(f"/api/certs/agent/{cert_id}/revoke", json={"reason": "disputed"})
    return cert_id


async def test_appeal_full_flow(client: AsyncClient) -> None:
    cert_id = await _issue_and_revoke_cert(client)
    appeal = (
        await client.post(
            "/api/appeals/",
            json={"target_id": cert_id, "appellant": "david_kim", "grounds": "false positive"},
        )
    ).json()
    assert appeal["status"] == "open"
    # The original approver was recorded (admin revoked it).
    original = appeal["original_approver"]

    # A second reviewer that equals the original approver is rejected.
    if original:
        bad = await client.post(
            f"/api/appeals/{appeal['id']}/assign", json={"reviewer": original}
        )
        assert bad.status_code == 400

    assigned = (
        await client.post(
            f"/api/appeals/{appeal['id']}/assign", json={"reviewer": "second_reviewer"}
        )
    ).json()
    assert assigned["status"] == "under_review" and assigned["second_reviewer"] == "second_reviewer"

    resolved = (
        await client.post(
            f"/api/appeals/{appeal['id']}/resolve",
            json={"decision": "overturned", "note": "evidence supports appellant"},
        )
    ).json()
    assert resolved["status"] == "overturned" and resolved["reviewer_decision"] == "overturned"


async def test_appeal_window_closed(client: AsyncClient, db_session: AsyncSession) -> None:
    from src.models.cert import CertLifecycleEvent

    cert_id = await _issue_and_revoke_cert(client)
    # Backdate the decision beyond the 7-day appeal window.
    for ev in (await db_session.execute(select(CertLifecycleEvent))).scalars().all():
        ev.timestamp = utcnow() - timedelta(days=10)
    await db_session.commit()
    resp = await client.post(
        "/api/appeals/",
        json={"target_id": cert_id, "appellant": "david_kim", "grounds": "late"},
    )
    assert resp.status_code == 400 and "window" in resp.json()["detail"].lower()


async def test_resolve_requires_reviewer_or_escalation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    cert_id = await _issue_and_revoke_cert(client)
    appeal = (
        await client.post(
            "/api/appeals/",
            json={"target_id": cert_id, "appellant": "david_kim", "grounds": "x"},
        )
    ).json()
    # No reviewer assigned + not escalated → cannot resolve.
    resp = await client.post(
        f"/api/appeals/{appeal['id']}/resolve", json={"decision": "upheld"}
    )
    assert resp.status_code == 400
    # Founder escalation lets it resolve without a second reviewer.
    ok = await client.post(
        f"/api/appeals/{appeal['id']}/resolve",
        json={"decision": "upheld", "escalate_to_founder": True},
    )
    assert ok.status_code == 200 and ok.json()["escalated_to_founder"] is True


async def test_appeals_list(client: AsyncClient, db_session: AsyncSession) -> None:
    cert_id = await _issue_and_revoke_cert(client)
    await client.post(
        "/api/appeals/",
        json={"target_id": cert_id, "appellant": "david_kim", "grounds": "x"},
    )
    appeals = (await client.get("/api/appeals/")).json()["appeals"]
    assert len(appeals) >= 1
    assert (await db_session.execute(select(Appeal))).scalars().first() is not None
