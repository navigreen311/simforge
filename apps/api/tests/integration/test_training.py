"""Integration: agent training — weak run → proposal → approve → certs re-cert (ADR-0026)."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.run import Run
from src.models.scorecard import Scorecard
from src.services.training.proposals import _bump_version

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")
FORGE_CAP = "cre-forge.call_center.outbound_seller_outreach"


def test_bump_version() -> None:
    assert _bump_version("prompt.v1") == "prompt.v2"
    assert _bump_version("prompt.v9") == "prompt.v10"
    assert _bump_version("prompt") == "prompt.v2"


async def _weaken_p7(db_session: AsyncSession, run_id: str) -> None:
    run = (await db_session.execute(select(Run).where(Run.runId == run_id))).scalar_one()
    card = (
        await db_session.execute(select(Scorecard).where(Scorecard.runId == run.id))
    ).scalar_one()
    card.p7CustomerExperience = 0.30  # weak — below the 0.60 training threshold
    await db_session.commit()


async def test_good_run_yields_no_proposal(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    run = (await client.post("/api/scenarios/scn.gs.src.001/run")).json()
    body = (await client.post(f"/api/training/proposals/from-run/{run['run_id']}")).json()
    assert body["proposal"] is None  # stub dims are all >= 0.75, nothing to improve


async def test_weak_run_proposes_and_approval_suspends_cert(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    run = (await client.post("/api/scenarios/scn.gs.src.001/run")).json()
    rid = run["run_id"]

    # Issue a cert (pins agent_prompt_version=prompt.v1) BEFORE weakening the (already-gated) card.
    issue = await client.post(
        "/api/certs/agent/issue",
        json={
            "agent_village_id": "david_kim",
            "forge_cap": FORGE_CAP,
            "tier": "foundational",
            "battery_run_ids": [rid],
            "approver_id": "ivan",
            "pack_id": "pack.greenstone.v1",
        },
    )
    assert issue.status_code == 200, issue.text
    cert_id = issue.json()["cert"]["id"]

    await _weaken_p7(db_session, rid)

    # Training surfaces a proposal targeting the weak dim.
    proposal = (await client.post(f"/api/training/proposals/from-run/{rid}")).json()["proposal"]
    assert proposal is not None
    assert proposal["weakDims"] == ["p7_cx"]
    assert proposal["currentPromptVersion"] == "prompt.v1"
    assert proposal["proposedPromptVersion"] == "prompt.v2"
    assert proposal["status"] == "proposed" and proposal["autoApplied"] is False

    # It shows in the list, still just proposed (not applied).
    listed = (await client.get("/api/training/proposals", params={"status": "proposed"})).json()
    assert any(p["id"] == proposal["id"] for p in listed)

    # Approve → promote prompt version + suspend the cert pinned to the old version.
    approve = (
        await client.post(
            f"/api/training/proposals/{proposal['id']}/approve", json={"reviewer": "ivan"}
        )
    ).json()
    assert approve["status"] == "approved"
    assert approve["new_prompt_version"] == "prompt.v2"
    assert FORGE_CAP in approve["certs_suspended"]

    # The cert is now suspended → the PDP denies it (governance enforced, not bypassed).
    assert (await client.get(f"/api/certs/agent/{cert_id}")).json()["status"] == "suspended"
    d = (
        await client.post(
            "/api/pdp/decide", json={"subject_agent_id": "david_kim", "action": FORGE_CAP}
        )
    ).json()
    assert d["decision"] == "deny" and d["reason_code"] == "cert_suspended"


async def test_enriched_shows_blast_radius_preview_then_applied(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The enriched surface previews which certs approval WOULD suspend, then what it DID."""
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    run = (await client.post("/api/scenarios/scn.gs.src.001/run")).json()
    rid = run["run_id"]
    await client.post(
        "/api/certs/agent/issue",
        json={
            "agent_village_id": "david_kim",
            "forge_cap": FORGE_CAP,
            "tier": "foundational",
            "battery_run_ids": [rid],
            "approver_id": "ivan",
            "pack_id": "pack.greenstone.v1",
        },
    )
    await _weaken_p7(db_session, rid)
    proposal = (await client.post(f"/api/training/proposals/from-run/{rid}")).json()["proposal"]

    # PENDING → preview lists the cert approval would suspend, readable + not inferred.
    enriched = (await client.get("/api/training/proposals/enriched")).json()["proposals"]
    p = next(x for x in enriched if x["id"] == proposal["id"])
    assert p["agent_village_id"] == "david_kim" and p["agent_name"]
    assert p["scenario_title"]  # triggering run resolves to a readable title
    assert p["consequence"]["kind"] == "preview" and p["consequence"]["inferred"] is False
    assert FORGE_CAP in {c["cap"] for c in p["consequence"]["certs"]}

    # APPROVE (human-gated) → consequence flips to applied, listing the suspended cert (inferred).
    await client.post(
        f"/api/training/proposals/{proposal['id']}/approve", json={"reviewer": "ivan"}
    )
    enriched2 = (await client.get("/api/training/proposals/enriched")).json()["proposals"]
    p2 = next(x for x in enriched2 if x["id"] == proposal["id"])
    assert p2["consequence"]["kind"] == "applied" and p2["consequence"]["inferred"] is True
    assert FORGE_CAP in {c["cap"] for c in p2["consequence"]["certs"]}


async def test_reject_proposal(client: AsyncClient, db_session: AsyncSession) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    run = (await client.post("/api/scenarios/scn.gs.src.001/run")).json()
    await _weaken_p7(db_session, run["run_id"])
    proposal = (await client.post(f"/api/training/proposals/from-run/{run['run_id']}")).json()[
        "proposal"
    ]
    rej = (
        await client.post(
            f"/api/training/proposals/{proposal['id']}/reject",
            json={"reviewer": "ivan", "reason": "guidance too generic"},
        )
    ).json()
    assert rej["status"] == "rejected"
    assert rej["reason"] == "guidance too generic"  # echoed (not persisted — no column yet)
    # A rejected proposal can't be approved.
    again = await client.post(
        f"/api/training/proposals/{proposal['id']}/approve", json={"reviewer": "ivan"}
    )
    assert again.status_code == 400
