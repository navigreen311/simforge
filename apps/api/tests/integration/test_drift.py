"""Integration test: Drift Canary — Forge version drift auto-suspends a pinned cert (ADR-0017)."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")
FORGE_CAP = "cre-forge.call_center.outbound_seller_outreach"


async def _issue_cert(client: AsyncClient) -> tuple[str, str]:
    """Run a passing scenario, issue a cert, return (cert_id, pinned forge version)."""
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
    pinned = issue["snapshot"]["pinnedVersions"]["forge_versions"]["cre-forge"]
    return issue["cert"]["id"], pinned


async def test_cert_pins_real_forge_version(client: AsyncClient) -> None:
    _, pinned = await _issue_cert(client)
    # The cert pins the Forge's real current version, not a placeholder.
    assert pinned == "cre-forge.dealdesk.v1"


async def test_no_drift_when_version_matches(client: AsyncClient) -> None:
    cert_id, _ = await _issue_cert(client)
    status = (await client.get("/api/drift/status")).json()
    assert status["drifted_certs"] == 0
    scan = (await client.post("/api/drift/scan")).json()
    assert scan["suspended"] == 0
    # Cert stays active.
    assert (await client.get(f"/api/certs/agent/{cert_id}")).json()["status"] == "active"


class _BumpedAdapter:
    """A stand-in Forge adapter reporting a *newer* version — simulates a Forge upgrade."""

    async def get_current_version(self) -> str:
        return "cre-forge.dealdesk.v2"


async def test_forge_drift_auto_suspends_and_demotes(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cert_id, _ = await _issue_cert(client)
    # Autonomy advanced to L2 on issue.
    assert (await client.get("/api/agents/david_kim")).json()["currentAutonomyLevel"] == "L2"

    # The cre-forge sandbox is upgraded to v2 — its reported version now differs from the pin.
    monkeypatch.setattr(
        "src.services.drift.canary.get_forge_adapter",
        lambda forge: _BumpedAdapter() if forge == "cre-forge" else None,
    )

    # Dry-run status surfaces the drift without acting.
    status = (await client.get("/api/drift/status")).json()
    assert status["drifted_certs"] == 1
    finding = next(f for f in status["findings"] if f["status"] == "drift")
    assert finding["pinned_version"] == "cre-forge.dealdesk.v1"
    assert finding["current_version"] == "cre-forge.dealdesk.v2"
    # Dry run did NOT suspend.
    assert (await client.get(f"/api/certs/agent/{cert_id}")).json()["status"] == "active"

    # The real scan suspends the drifted cert and demotes the agent.
    scan = (await client.post("/api/drift/scan")).json()
    assert scan["suspended"] == 1
    assert (await client.get(f"/api/certs/agent/{cert_id}")).json()["status"] == "suspended"
    assert (await client.get("/api/agents/david_kim")).json()["currentAutonomyLevel"] == "L1"


async def test_suspended_cert_reinstated_by_recert(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A drift-suspended cert recovers via re-certification against the current version matrix."""
    cert_id, pinned = await _issue_cert(client)
    # Drift → suspend + demote to L1. (Only the drift canary's Forge lookup is patched; the cert
    # registry's re-pin during reinstate uses the real adapter → pins the current v1 again.)
    monkeypatch.setattr(
        "src.services.drift.canary.get_forge_adapter",
        lambda forge: _BumpedAdapter() if forge == "cre-forge" else None,
    )
    assert (await client.post("/api/drift/scan")).json()["suspended"] == 1
    assert (await client.get(f"/api/certs/agent/{cert_id}")).json()["status"] == "suspended"
    assert (await client.get("/api/agents/david_kim")).json()["currentAutonomyLevel"] == "L1"

    # Re-issue is blocked (a suspended cert occupies the pair) — must reinstate instead.
    dup = await client.post(
        "/api/certs/agent/issue",
        json={
            "agent_village_id": "david_kim",
            "forge_cap": "cre-forge.call_center.outbound_seller_outreach",
            "tier": "foundational",
            "battery_run_ids": [
                (await client.post("/api/scenarios/scn.gs.src.001/run")).json()["run_id"]
            ],
            "approver_id": "ivan",
            "pack_id": "pack.greenstone.v1",
        },
    )
    assert dup.status_code == 400
    assert "reinstate" in dup.json()["detail"].lower()

    # A fresh passing battery reinstates: cert → active, re-pins the CURRENT forge version,
    # and autonomy is restored to L2.
    fresh_run = (await client.post("/api/scenarios/scn.gs.src.001/run")).json()["run_id"]
    reinstate = await client.post(
        f"/api/certs/agent/{cert_id}/reinstate",
        json={"battery_run_ids": [fresh_run], "approver_id": "ivan"},
    )
    assert reinstate.status_code == 200, reinstate.text
    body = reinstate.json()
    assert body["cert"]["status"] == "active"
    assert body["autonomy_from"] == "L1" and body["autonomy_to"] == "L2"
    # New snapshot pins the current version (still v1 here — no real drift now).
    assert body["snapshot"]["pinnedVersions"]["forge_versions"]["cre-forge"] == pinned
    assert (await client.get("/api/agents/david_kim")).json()["currentAutonomyLevel"] == "L2"

    # And the signature on the new snapshot verifies.
    verify = (await client.get(f"/api/snapshots/{body['snapshot']['snapshotId']}/verify")).json()
    assert verify["valid"] is True


async def test_reinstate_rejects_non_suspended_cert(client: AsyncClient) -> None:
    cert_id, _ = await _issue_cert(client)  # active, not suspended
    fresh_run = (await client.post("/api/scenarios/scn.gs.src.001/run")).json()["run_id"]
    resp = await client.post(
        f"/api/certs/agent/{cert_id}/reinstate",
        json={"battery_run_ids": [fresh_run], "approver_id": "ivan"},
    )
    assert resp.status_code == 400
    assert "suspended" in resp.json()["detail"].lower()
