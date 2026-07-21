"""Integration tests for the constitution/amendment workflow + registry endpoints."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.governance import get_current_constitution, ratify_constitution
from src.services.governance.amendment import propose_amendment, ratify_amendment


async def test_constitution_ratify_and_current(db_session: AsyncSession) -> None:
    await ratify_constitution(db_session, "v1.0.0", "ivan", "articles: []")
    await db_session.commit()
    c = await get_current_constitution(db_session)
    assert c is not None and c.version == "v1.0.0"


async def test_amendment_cooling_then_ratify(db_session: AsyncSession) -> None:
    await ratify_constitution(db_session, "v1.0.0", "ivan", "base")
    await db_session.commit()

    amendment = await propose_amendment(db_session, "ivan", "diff: x", cooling_days=0)
    assert amendment.status == "in_cooling"

    result = await ratify_amendment(db_session, amendment.amendmentId, "ivan")
    assert result["new_version"] == "v1.0.1"
    assert result["superseded"] == "v1.0.0"

    current = await get_current_constitution(db_session)
    assert current.version == "v1.0.1"


async def test_constitution_endpoints(client: AsyncClient) -> None:
    # No constitution seeded in the test DB → 404
    assert (await client.get("/api/constitution/current")).status_code == 404
    # Safe-mode toggle
    on = await client.post("/api/constitution/safe-mode", json={"active": True, "reason": "drill"})
    assert on.status_code == 200 and on.json()["active"] is True
    off = await client.post("/api/constitution/safe-mode", json={"active": False})
    assert off.json()["active"] is False


async def test_cert_issuance_creates_lineage(client: AsyncClient) -> None:
    from pathlib import Path

    repo = Path(__file__).resolve().parents[4]
    await client.post("/api/packs/", json={"pack_dir": str(repo / "packs" / "greenstone" / "v1")})
    run = (await client.post("/api/scenarios/scn.gs.src.001/run")).json()
    issue = (
        await client.post(
            "/api/certs/agent/issue",
            json={
                "agent_village_id": "david_kim",
                "forge_cap": "cre-forge.call_center.outbound_seller_outreach",
                "tier": "foundational",
                "battery_run_ids": [run["run_id"]],
                "approver_id": "ivan",
                "pack_id": "pack.greenstone.v1",
            },
        )
    ).json()
    cert_urn = f"urn:gc:village:cert:{issue['cert']['id']}"
    edges = (await client.get(f"/api/lineage/from/{cert_urn}")).json()["edges"]
    relations = {e["relation"] for e in edges}
    assert {"produced_by", "derived_from", "pinned_to", "evidenced_by"} <= relations
