"""Incident Command report (ADR-0040)."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")
FORGE_CAP = "cre-forge.call_center.outbound_seller_outreach"


# Safe mode is now DB-backed (§11.7); the test DB is fresh per test, so no reset fixture is needed.


async def test_incident_report_clean(client: AsyncClient) -> None:
    resp = await client.get("/api/incident/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["total_incidents"] == 0
    assert body["safe_mode"]["active"] is False


async def test_safe_mode_is_a_critical_incident(client: AsyncClient) -> None:
    await client.post(
        "/api/constitution/safe-mode",
        json={"active": True, "reason": "drill", "scope_type": "forge", "scope_value": "cre-forge"},
    )
    body = (await client.get("/api/incident/status")).json()
    assert body["status"] == "critical"
    sm = next(i for i in body["incidents"] if i["kind"] == "safe_mode")
    assert sm["severity"] == "critical"
    assert sm["blast_radius"]["departments"] == ["forge:cre-forge"]


async def test_revoked_cert_incident_with_blast_radius(client: AsyncClient) -> None:
    # Issue a cert, then revoke it → a governance incident with the agent + cap in the blast radius.
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    run = (await client.post("/api/scenarios/scn.gs.src.001/run")).json()
    issue = (
        await client.post(
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
    ).json()
    await client.post(f"/api/certs/agent/{issue['cert']['id']}/revoke", json={"reason": "policy"})

    body = (await client.get("/api/incident/status")).json()
    assert body["status"] == "degraded"
    revoked = next(i for i in body["incidents"] if i["kind"] == "certs_revoked")
    assert revoked["severity"] == "high"
    assert "david_kim" in revoked["blast_radius"]["agents"]
    assert FORGE_CAP in revoked["blast_radius"]["forge_caps"]
    assert "Engineering" in revoked["blast_radius"]["departments"]

    # Presentation-only enrichment (derived; no data changed): capability labels for every cap,
    # the agent's display name, and a demo-driven flag from the underlying cert reasons.
    assert revoked["cap_labels"][FORGE_CAP]["label"] == "Outbound Seller Outreach"
    assert revoked["cap_labels"][FORGE_CAP]["forge"] == "cre-forge"
    assert revoked["agent_names"]["david_kim"] == "David Kim"
    # this cert was revoked for reason "policy" (a real reason), so NOT demo-driven
    assert revoked["demo_driven"] is False


async def test_demo_reason_marks_incident_demo_driven(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    run = (await client.post("/api/scenarios/scn.gs.src.001/run")).json()
    issue = (
        await client.post(
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
    ).json()
    await client.post(f"/api/certs/agent/{issue['cert']['id']}/revoke", json={"reason": "demo"})

    body = (await client.get("/api/incident/status")).json()
    revoked = next(i for i in body["incidents"] if i["kind"] == "certs_revoked")
    assert revoked["demo_driven"] is True  # reason=demo → seed/demo-driven, not a real outage
