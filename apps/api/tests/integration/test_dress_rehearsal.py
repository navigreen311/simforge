"""Dress Rehearsal Protocol (§15): entry/exit criteria (real + seams), gated signed sign-off."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.pack import Pack
from src.models.village_fingerprint import VillageFingerprint
from src.services.governance import ratify_constitution
from src.utils.time import utcnow

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")


async def test_entry_criteria_reports_each_check(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    res = (await client.get("/api/dress-rehearsal/pack.greenstone.v1/entry-criteria")).json()
    names = {c["name"] for c in res["criteria"]}
    assert names == {
        "pack_has_scenarios",
        "pack_signed",
        "forge_parity",
        "fingerprint_stable",
        "zero_p0_gaps",
        "constitution_ratified",
    }
    # forge_parity is honestly flagged as a seam.
    parity = next(c for c in res["criteria"] if c["name"] == "forge_parity")
    assert parity["is_seam"] is True
    # Scenarios exist; the pack has them.
    assert next(c for c in res["criteria"] if c["name"] == "pack_has_scenarios")["passed"] is True


async def test_entry_criteria_all_pass_when_prerequisites_met(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    # Satisfy the real criteria: sign the pack, ratify a constitution, seed a stable fingerprint.
    pack = (
        await db_session.execute(select(Pack).where(Pack.packId == "pack.greenstone.v1"))
    ).scalar_one()
    pack.signedBy = "acquisitions_principal"
    pack.signedAt = utcnow()
    db_session.add(
        VillageFingerprint(
            fingerprint="fp-stable",
            capturedAt=utcnow() - timedelta(days=10),
            paths=[],
            isCurrent=True,
        )
    )
    await ratify_constitution(db_session, "v1.0.0", "ivan", "articles: []")
    await db_session.commit()

    started = (await client.post("/api/dress-rehearsal/pack.greenstone.v1/start")).json()
    assert started["status"] == "entry_passed", started["entry_results"]


async def test_full_flow_entry_exit_signoff(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    # A blind, gate-passing run so exit criteria (gate + blind minimum) hold.
    await client.post("/api/scenarios/scn.gs.src.001/run", params={"blind": True})
    pack = (
        await db_session.execute(select(Pack).where(Pack.packId == "pack.greenstone.v1"))
    ).scalar_one()
    pack.signedBy = "acquisitions_principal"
    db_session.add(
        VillageFingerprint(
            fingerprint="fp2", capturedAt=utcnow() - timedelta(days=10), paths=[], isCurrent=True
        )
    )
    await ratify_constitution(db_session, "v1.0.0", "ivan", "a: 1")
    await db_session.commit()
    # Red-team passes is a seam — set it to meet the ≥2 requirement.
    monkeypatch.setattr(settings, "dress_rehearsal_redteam_passes", 2)

    started = (await client.post("/api/dress-rehearsal/pack.greenstone.v1/start")).json()
    assert started["status"] == "entry_passed"
    exited = (await client.post(f"/api/dress-rehearsal/{started['id']}/exit")).json()
    assert exited["status"] == "exit_passed", exited["exit_results"]

    signed = (
        await client.post(
            f"/api/dress-rehearsal/{started['id']}/signoff",
            json={"role": "acquisitions_principal", "signer_id": "ivan"},
        )
    ).json()
    assert signed["status"] == "signed"
    assert len(signed["signoffs"]) == 1
    assert signed["signoffs"][0]["signature"]  # Ed25519-signed attestation


async def test_signoff_blocked_before_exit(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    started = (await client.post("/api/dress-rehearsal/pack.greenstone.v1/start")).json()
    # In a fresh dev DB, entry fails (no fingerprint/signed pack) → sign-off blocked.
    resp = await client.post(
        f"/api/dress-rehearsal/{started['id']}/signoff",
        json={"role": "x", "signer_id": "y"},
    )
    assert resp.status_code == 400
