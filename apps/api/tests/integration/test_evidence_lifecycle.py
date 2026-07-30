"""Evidence lifecycle (§12.3): Merkle chain, tamper detection, legal hold, redaction, audit."""

from __future__ import annotations

from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.evidence import EvidenceRecord
from src.services.evidence import (
    purge_expired,
    redact_bundle,
    register_evidence,
    set_legal_hold,
    verify_chain,
)
from src.services.evidence.lifecycle import default_redaction_for
from src.utils.time import utcnow

REPO_ROOT = None


def _gs() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parents[4] / "packs" / "greenstone" / "v1")


async def test_chain_grows_and_verifies(db_session: AsyncSession) -> None:
    for i in range(3):
        await register_evidence(
            db_session, bundle_id=f"b{i}", ref=f"file:///b{i}", content_hash=f"hash{i}"
        )
    await db_session.commit()
    chain = await verify_chain(db_session)
    assert chain.intact is True and chain.length == 3 and chain.break_at is None


async def test_tamper_is_detected(db_session: AsyncSession) -> None:
    await register_evidence(db_session, bundle_id="t0", ref="file:///t0", content_hash="h0")
    await register_evidence(db_session, bundle_id="t1", ref="file:///t1", content_hash="h1")
    await db_session.commit()
    # Tamper with a stored content hash without recomputing the anchor.
    rec = (
        await db_session.execute(select(EvidenceRecord).where(EvidenceRecord.bundleId == "t0"))
    ).scalar_one()
    rec.contentHash = "tampered"
    await db_session.commit()
    chain = await verify_chain(db_session)
    assert chain.intact is False and chain.break_at == "t0"


async def test_legal_hold_blocks_purge(db_session: AsyncSession) -> None:
    await register_evidence(db_session, bundle_id="h0", ref="file:///h0", content_hash="h0")
    await register_evidence(db_session, bundle_id="h1", ref="file:///h1", content_hash="h1")
    await db_session.commit()
    # Expire both retention deadlines.
    for r in (await db_session.execute(select(EvidenceRecord))).scalars().all():
        r.retentionUntil = utcnow() - timedelta(days=1)
    await db_session.commit()
    # Put h0 on legal hold → only h1 purges.
    await set_legal_hold(db_session, "h0", True, "counsel")
    purged = await purge_expired(db_session)
    assert purged == ["h1"]


def test_redaction_classes() -> None:
    bundle = {"subject": "david_kim", "transcript": ["x"], "cost_usd": 1.2, "note": "keep"}
    phi = redact_bundle(bundle, "phi_synthetic")
    assert phi["transcript"] == "[REDACTED]" and phi["subject"] == "[REDACTED]"
    assert phi["note"] == "keep"
    fin = redact_bundle(bundle, "financial")
    assert fin["cost_usd"] == "[REDACTED]" and fin["subject"] == "david_kim"
    assert redact_bundle(bundle, "standard") == bundle


def test_default_redaction_for_phi() -> None:
    assert default_redaction_for(True) == "phi_synthetic"
    assert default_redaction_for(False) == "standard"


async def test_cert_issuance_records_evidence_and_access_log(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post("/api/packs/", json={"pack_dir": _gs()})
    run = (await client.post("/api/scenarios/scn.gs.src.001/run")).json()
    issue = await client.post(
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
    assert issue.status_code == 200, issue.text
    snapshot_id = issue.json()["snapshot"]["snapshotId"]  # "certsnap:..." = the evidence bundle id

    # An evidence record was created + chained.
    rec = (await client.get(f"/api/evidence/{snapshot_id}")).json()
    assert rec["bundle_id"] == snapshot_id and rec["chain_anchor"]
    # Chain verifies.
    assert (await client.get("/api/evidence/chain/verify")).json()["intact"] is True
    # Redacted export logs an access.
    exp = (await client.get(f"/api/evidence/{snapshot_id}/export")).json()
    assert exp["redaction_class"] in ("standard", "phi_synthetic")
    detail = (await client.get(f"/api/evidence/{snapshot_id}")).json()
    assert len(detail["access_log"]) >= 1
