"""Integration: PDP turns issued certs into runtime authorization decisions (ADR-0024)."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")
FORGE_CAP = "cre-forge.call_center.outbound_seller_outreach"


async def _issue_cert(client: AsyncClient) -> str:
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
    assert issue.status_code == 200, issue.text
    return issue.json()["cert"]["id"]


async def test_uncertified_action_denied(client: AsyncClient) -> None:
    d = (
        await client.post(
            "/api/pdp/decide",
            json={"subject_agent_id": "david_kim", "action": FORGE_CAP},
        )
    ).json()
    assert d["decision"] == "deny" and d["reason_code"] == "no_certification"
    assert d["fail_policy"] == "fail_closed"


async def test_active_cert_at_l2_downgrades(client: AsyncClient) -> None:
    await _issue_cert(client)  # first cert promotes david_kim L1 → L2
    d = (
        await client.post(
            "/api/pdp/decide",
            json={"subject_agent_id": "david_kim", "action": FORGE_CAP},
        )
    ).json()
    # L2 = draft only → produce a draft, not a live action.
    assert d["decision"] == "downgrade_and_retry" and d["reason_code"] == "draft_only_l2"


async def test_revoked_cert_denies_and_demotes(client: AsyncClient) -> None:
    cert_id = await _issue_cert(client)
    await client.post(f"/api/certs/agent/{cert_id}/revoke", json={"reason": "policy"})
    d = (
        await client.post(
            "/api/pdp/decide",
            json={"subject_agent_id": "david_kim", "action": FORGE_CAP},
        )
    ).json()
    # Revocation both sets cert status and demotes autonomy → deny wins on cert status.
    assert d["decision"] == "deny" and d["reason_code"] == "cert_revoked"


async def test_effective_permissions_lists_decisions(client: AsyncClient) -> None:
    await _issue_cert(client)
    body = (await client.get("/api/pdp/agent/david_kim/effective")).json()
    assert body["autonomy_level"] == "L2"
    perms = {p["action"]: p for p in body["permissions"]}
    assert FORGE_CAP in perms
    assert perms[FORGE_CAP]["decision"] == "downgrade_and_retry"
    assert perms[FORGE_CAP]["cert_status"] == "active"
    # Presentation-only enrichment (derived; no data changed): friendly capability label reused
    # from the shared catalog — same source as Readiness/Certs/Incident.
    assert perms[FORGE_CAP]["capability_label"] == "Outbound Seller Outreach"
    assert perms[FORGE_CAP]["capability_forge"] == "cre-forge"


async def test_unknown_agent_effective_404(client: AsyncClient) -> None:
    resp = await client.get("/api/pdp/agent/ghost/effective")
    assert resp.status_code == 404
