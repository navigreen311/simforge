"""Integration test: the full certification payoff — gate pass → signed cert → autonomy."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.department import Department

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")
FORGE_CAP = "cre-forge.call_center.outbound_seller_outreach"


async def _passing_run(client: AsyncClient) -> str:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    run = (await client.post("/api/scenarios/scn.gs.src.001/run")).json()
    # Confirm it passed the gate (prerequisite for cert issuance)
    card = (await client.get(f"/api/runs/{run['run_id']}/scorecard")).json()
    assert card["readiness_gate_passed"] is True, card
    return run["run_id"]


async def test_full_certification_flow(client: AsyncClient) -> None:
    run_id = await _passing_run(client)

    # Agent starts at L1
    assert (await client.get("/api/agents/david_kim")).json()["currentAutonomyLevel"] == "L1"

    issue = await client.post(
        "/api/certs/agent/issue",
        json={
            "agent_village_id": "david_kim",
            "forge_cap": FORGE_CAP,
            "tier": "foundational",
            "battery_run_ids": [run_id],
            "approver_id": "ivan",
            "pack_id": "pack.greenstone.v1",
        },
    )
    assert issue.status_code == 200, issue.text
    body = issue.json()
    assert body["cert"]["status"] == "active"
    assert body["snapshot"]["snapshotId"].startswith("certsnap:")
    assert body["autonomy_from"] == "L1" and body["autonomy_to"] == "L2"
    cert_id = body["cert"]["id"]
    snapshot_id = body["snapshot"]["snapshotId"]

    # Autonomy advanced to L2
    assert (await client.get("/api/agents/david_kim")).json()["currentAutonomyLevel"] == "L2"

    # Signature verifies
    verify = (await client.get(f"/api/snapshots/{snapshot_id}/verify")).json()
    assert verify["valid"] is True

    # External attestation confirms
    attest = (await client.get(f"/api/attest/cert/{cert_id}")).json()
    assert attest["signature_valid"] is True and attest["status"] == "active"

    # Public keys published
    keys = (await client.get("/api/attest/public-keys")).json()
    assert len(keys["keys"]) == 1 and "BEGIN PUBLIC KEY" in keys["keys"][0]["public_key_pem"]


async def test_duplicate_cert_rejected(client: AsyncClient) -> None:
    run_id = await _passing_run(client)
    payload = {
        "agent_village_id": "david_kim",
        "forge_cap": FORGE_CAP,
        "tier": "foundational",
        "battery_run_ids": [run_id],
        "approver_id": "ivan",
        "pack_id": "pack.greenstone.v1",
    }
    assert (await client.post("/api/certs/agent/issue", json=payload)).status_code == 200
    dup = await client.post("/api/certs/agent/issue", json=payload)
    assert dup.status_code == 400


async def test_revoke_demotes_autonomy(client: AsyncClient) -> None:
    run_id = await _passing_run(client)
    issue = (
        await client.post(
            "/api/certs/agent/issue",
            json={
                "agent_village_id": "david_kim",
                "forge_cap": FORGE_CAP,
                "tier": "foundational",
                "battery_run_ids": [run_id],
                "approver_id": "ivan",
                "pack_id": "pack.greenstone.v1",
            },
        )
    ).json()
    cert_id = issue["cert"]["id"]

    revoke = await client.post(
        f"/api/certs/agent/{cert_id}/revoke", json={"reason": "policy change"}
    )
    assert revoke.status_code == 200
    assert revoke.json()["status"] == "revoked"
    # Autonomy demoted L2 → L1
    assert (await client.get("/api/agents/david_kim")).json()["currentAutonomyLevel"] == "L1"


async def test_crl_populates_on_revocation(client: AsyncClient) -> None:
    """A revoked cert appears in the CRL (structured) and in /public-keys' crl list (ADR-0038)."""
    run_id = await _passing_run(client)
    issue = (
        await client.post(
            "/api/certs/agent/issue",
            json={
                "agent_village_id": "david_kim",
                "forge_cap": FORGE_CAP,
                "tier": "foundational",
                "battery_run_ids": [run_id],
                "approver_id": "ivan",
                "pack_id": "pack.greenstone.v1",
            },
        )
    ).json()
    cert_id = issue["cert"]["id"]
    snapshot_id = issue["cert"]["certSnapshotId"]

    # Before revocation the CRL is empty and the snapshot is not listed.
    assert (await client.get("/api/attest/crl")).json()["total"] == 0
    assert snapshot_id not in (await client.get("/api/attest/public-keys")).json()["crl"]

    await client.post(f"/api/certs/agent/{cert_id}/revoke", json={"reason": "policy change"})

    crl = (await client.get("/api/attest/crl")).json()
    assert crl["total"] == 1
    entry = crl["entries"][0]
    assert entry["cert_id"] == cert_id
    assert entry["status"] == "revoked"
    assert entry["reason"] == "policy change"
    assert entry["at"] is not None

    # And the published /public-keys CRL lists the revoked snapshot id.
    keys = (await client.get("/api/attest/public-keys")).json()
    assert entry["snapshot_id"] in keys["crl"]


async def test_issue_rejects_failing_battery(client: AsyncClient) -> None:
    # A crisis run fails the gate → cannot be used as a battery
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    run = (await client.post("/api/scenarios/scn.gs.crisis.003/run")).json()
    resp = await client.post(
        "/api/certs/agent/issue",
        json={
            "agent_village_id": "david_kim",
            "forge_cap": "cre-forge.deals.title",
            "tier": "advanced_crisis",
            "battery_run_ids": [run["run_id"]],
            "approver_id": "ivan",
            "pack_id": "pack.greenstone.v1",
        },
    )
    assert resp.status_code == 400
    assert "gate" in resp.json()["detail"].lower()


async def _dept_key_for(db_session: AsyncSession, village_agent_id: str) -> str:
    agent = (
        await db_session.execute(select(Agent).where(Agent.villageAgentId == village_agent_id))
    ).scalar_one()
    dept = (
        await db_session.execute(select(Department).where(Department.id == agent.departmentId))
    ).scalar_one()
    return dept.villageKey


async def test_dept_cert_lifecycle(client: AsyncClient, db_session: AsyncSession) -> None:
    """DeptCert (D2 dual certification): prerequisites → issue → coverage cascade on revoke."""
    run_id = await _passing_run(client)  # foundational src.001, david_kim
    # Issue david_kim's AgentCert — this is the prerequisite coverage for the dept.
    issue = await client.post(
        "/api/certs/agent/issue",
        json={
            "agent_village_id": "david_kim",
            "forge_cap": FORGE_CAP,
            "tier": "foundational",
            "battery_run_ids": [run_id],
            "approver_id": "ivan",
            "pack_id": "pack.greenstone.v1",
        },
    )
    assert issue.status_code == 200, issue.text
    agent_cert_id = issue.json()["cert"]["id"]

    dept_key = await _dept_key_for(db_session, "david_kim")

    # Prerequisite status: 1 covering agent, satisfied at min=1.
    prereq = (
        await client.get(
            "/api/certs/dept/prerequisites",
            params={"department_key": dept_key, "forge_caps": FORGE_CAP},
        )
    ).json()
    assert prereq["covering_count"] == 1 and "david_kim" in prereq["covering_agents"]

    # A dept-wide Intermediate scenario that passes the gate (buy.002 is intermediate).
    dept_run = (await client.post("/api/scenarios/scn.gs.buy.002/run")).json()
    card = (await client.get(f"/api/runs/{dept_run['run_id']}/scorecard")).json()
    assert card["readiness_gate_passed"] is True, card

    # Issue the DeptCert (min=1 for the test cohort).
    dept_issue = await client.post(
        "/api/certs/dept/issue",
        json={
            "department_key": dept_key,
            "forge_context": "greenstone_seller_acquisition_ops",
            "tier": "intermediate",
            "dept_battery_run_ids": [dept_run["run_id"]],
            "approver_id": "ivan",
            "pack_id": "pack.greenstone.v1",
            "required_forge_caps": [FORGE_CAP],
            "prerequisite_min": 1,
        },
    )
    assert dept_issue.status_code == 200, dept_issue.text
    dbody = dept_issue.json()
    assert dbody["cert"]["status"] == "active"
    assert dbody["cert"]["forgeContext"] == "greenstone_seller_acquisition_ops"
    assert agent_cert_id in dbody["cert"]["prerequisiteAgentCertIds"]
    assert dbody["snapshot"]["snapshotId"].startswith("certsnap:")
    dept_cert_id = dbody["cert"]["id"]

    # It shows in the dept-cert list.
    listed = (await client.get("/api/certs/dept", params={"department_key": dept_key})).json()
    assert any(c["id"] == dept_cert_id and c["status"] == "active" for c in listed["items"])

    # Revoking the underlying AgentCert drops coverage below min → DeptCert auto-suspends (cascade).
    await client.post(f"/api/certs/agent/{agent_cert_id}/revoke", json={"reason": "test cascade"})
    after = (await client.get("/api/certs/dept", params={"department_key": dept_key})).json()
    dc = next(c for c in after["items"] if c["id"] == dept_cert_id)
    assert dc["status"] == "suspended"


async def test_dept_cert_rejects_unmet_prerequisites(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    dept_key = await _dept_key_for(db_session, "david_kim")
    # No agent certs issued → default min=3 unmet → issuance rejected.
    resp = await client.post(
        "/api/certs/dept/issue",
        json={
            "department_key": dept_key,
            "forge_context": "greenstone_seller_acquisition_ops",
            "tier": "intermediate",
            "dept_battery_run_ids": ["nonexistent"],
            "approver_id": "ivan",
            "pack_id": "pack.greenstone.v1",
        },
    )
    assert resp.status_code == 400
    assert "prerequisite" in resp.json()["detail"].lower()
