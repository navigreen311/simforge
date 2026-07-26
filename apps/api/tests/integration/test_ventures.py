"""Venture Registry API tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")


@pytest.fixture(autouse=True)
def _stub_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.config import settings

    monkeypatch.setattr(settings, "llm_provider", "stub")


async def test_registry_is_seeded(client: AsyncClient) -> None:
    body = (await client.get("/api/ventures/")).json()
    by_slug = {v["slug"]: v for v in body["items"]}
    # the three with packs are active with real flags; the new ones are empty + in_development
    assert by_slug["medlink-pro"]["status"] == "active"
    assert "hipaa" in by_slug["medlink-pro"]["defaultComplianceFlags"]
    assert by_slug["argus"]["status"] == "in_development"
    assert by_slug["argus"]["defaultComplianceFlags"] == []
    assert by_slug["argus"]["capabilityCount"] == 0
    expected = {"greenstone", "medlink-pro", "caregrid", "argus", "collingswood"}
    assert expected <= set(by_slug)
    assert "burkham-wickmont" in by_slug


async def test_venture_detail_counts_packs(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    d = (await client.get("/api/ventures/greenstone")).json()
    assert d["packCount"] == 1
    assert d["packs"][0]["packId"] == "pack.greenstone.v1"
    assert d["packs"][0]["scenarioCount"] == 3
    assert (await client.get("/api/ventures/nope")).status_code == 404


async def test_create_venture(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/ventures/",
        json={"name": "Wexford Labs", "slug": "wexford", "status": "in_development"},
    )
    assert resp.status_code == 201, resp.text
    v = resp.json()
    assert v["slug"] == "wexford"
    assert v["scenarioCode"] == "we"  # auto-derived from slug
    # now visible in the registry (so vocabulary/pack-create can use it)
    vocab = (await client.get("/api/scenario-bank/vocabulary")).json()
    assert "wexford" in vocab["packs"]


async def test_create_duplicate_rejected(client: AsyncClient) -> None:
    assert (
        await client.post("/api/ventures/", json={"name": "Argus", "slug": "argus"})
    ).status_code == 409


async def test_update_venture_status(client: AsyncClient) -> None:
    r = await client.patch(
        "/api/ventures/argus", json={"status": "active", "description": "Now live."}
    )
    assert r.status_code == 200
    assert r.json()["status"] == "active"
    assert r.json()["description"] == "Now live."


# ── Part B: spec upload ──────────────────────────────────────────────────────


async def test_upload_spec_creates_document(client: AsyncClient) -> None:
    body = b"Argus is a physical-security venture handling access control and incident triage " * 3
    r = await client.post(
        "/api/ventures/argus/specs",
        files={"file": ("argus-spec.txt", body, "text/plain")},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["specDocumentId"]
    # On the dev stub LLM the two passes fail honestly (no fabricated proposal/scenario), but the
    # spec document itself is stored for provenance.
    detail = (await client.get("/api/ventures/argus")).json()
    assert len(detail["specDocuments"]) == 1
    assert detail["specDocuments"][0]["filename"] == "argus-spec.txt"


async def test_upload_spec_unreadable_creates_nothing(client: AsyncClient) -> None:
    r = await client.post(
        "/api/ventures/argus/specs",
        files={"file": ("scan.png", b"\x89PNG binary", "image/png")},
    )
    assert r.json()["ok"] is False
    assert "Unsupported" in r.json()["error"]
    detail = (await client.get("/api/ventures/argus")).json()
    assert detail["specDocuments"] == []  # nothing stored


async def test_upload_spec_venture_404(client: AsyncClient) -> None:
    r = await client.post(
        "/api/ventures/nope/specs", files={"file": ("x.txt", b"hello world " * 10, "text/plain")}
    )
    assert r.status_code == 404


async def test_spec_scenarios_land_as_unreviewed_ai_drafts(db_session: AsyncSession) -> None:
    # A spec-produced scenario is an UNREVIEWED AI draft (reviewedBy null) in the review queue —
    # it does not auto-commit and does not enter a pack.
    from src.services.scenario_bank.promotion import create_draft

    draft = await create_draft(
        db_session,
        title="Access granted without an NDA",
        pack="argus",
        family="crisis",
        tier="foundational",
        situation="A vendor is granted access before the NDA is signed.",
        expected_behaviors=["require the NDA first"],
        adversarial_tactics=[],
        jurisdiction_flags=[],
        created_by="dev-ivan",
        ai_drafted=True,
        source_type="document",
        reviewed=False,
    )
    assert draft.status == "draft"
    assert draft.aiDrafted is True
    assert draft.reviewedBy is None  # unreviewed — awaits a human
    assert draft.scenarioId is None  # not committed, no scn.* id, not in any pack
