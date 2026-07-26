"""Scenario Bank browse/search/filter (Batch 1)."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bank_scenario import BankScenario
from src.utils.time import utcnow


async def _seed(session: AsyncSession) -> None:
    now = utcnow()
    session.add_all(
        [
            BankScenario(
                publicId="legacy_scn.gs.src.001",
                scenarioId="scn.gs.src.001",
                title="Cold outreach to a motivated seller",
                pack="greenstone",
                family="src",
                tier="foundational",
                situation="(legacy)",
                expectedBehaviors=["confirm TCPA consent"],
                status="committed",
                aiDrafted=False,
                sourceType="legacy",
                createdBy="legacy-backfill",
                createdAt=now,
                updatedAt=now,
            ),
            BankScenario(
                publicId="draft_abc123",
                scenarioId=None,
                title="HIPAA audit failure at a home-health agency",
                pack="caregrid",
                family="audit",
                tier="advanced_crisis",
                situation="A surprise CDPH audit finds an expired credential in the active pool.",
                expectedBehaviors=["escalate", "hard-block the expired credential"],
                status="draft",
                aiDrafted=True,
                sourceType="paste",
                sourceExcerpt="pasted incident writeup…",
                createdBy="ivan",
                createdAt=now,
                updatedAt=now,
            ),
        ]
    )
    await session.commit()


async def test_bank_lists_committed_and_draft(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    body = (await client.get("/api/scenario-bank/")).json()
    assert body["total"] == 2
    statuses = {r["scenarioId"] or r["publicId"]: r["status"] for r in body["items"]}
    assert statuses["scn.gs.src.001"] == "committed"
    assert statuses["draft_abc123"] == "draft"


async def test_bank_filters(client: AsyncClient, db_session: AsyncSession) -> None:
    await _seed(db_session)
    assert (await client.get("/api/scenario-bank/?status=draft")).json()["total"] == 1
    assert (await client.get("/api/scenario-bank/?ai_drafted=true")).json()["total"] == 1
    assert (await client.get("/api/scenario-bank/?ai_drafted=false")).json()["total"] == 1
    assert (await client.get("/api/scenario-bank/?pack=caregrid")).json()["total"] == 1
    assert (await client.get("/api/scenario-bank/?tier=foundational")).json()["total"] == 1
    assert (await client.get("/api/scenario-bank/?source_type=legacy")).json()["total"] == 1
    # search hits title, situation, and id
    assert (await client.get("/api/scenario-bank/?search=HIPAA")).json()["total"] == 1
    assert (await client.get("/api/scenario-bank/?search=scn.gs.src")).json()["total"] == 1


async def test_bank_counts_review_queue(client: AsyncClient, db_session: AsyncSession) -> None:
    await _seed(db_session)
    counts = (await client.get("/api/scenario-bank/counts")).json()
    assert counts["total"] == 2
    assert counts["by_status"]["committed"] == 1
    assert counts["awaiting_review"] == 1  # the one draft


async def test_bank_detail(client: AsyncClient, db_session: AsyncSession) -> None:
    await _seed(db_session)
    d = (await client.get("/api/scenario-bank/draft_abc123")).json()
    assert d["title"].startswith("HIPAA")
    assert d["situation"].startswith("A surprise CDPH audit")
    assert d["expectedBehaviors"] == ["escalate", "hard-block the expired credential"]
    assert d["sourceType"] == "paste"
    assert d["aiDrafted"] is True
    assert (await client.get("/api/scenario-bank/nope")).status_code == 404


# ── Batch 2: authoring + two-stage human promotion ──────────────────────────


async def test_vocabulary_endpoint(client: AsyncClient) -> None:
    v = (await client.get("/api/scenario-bank/vocabulary")).json()
    assert v["packs"] == ["greenstone", "medlink", "caregrid"]
    assert "crisis" in v["families"]
    assert "foundational" in v["tiers"]


_MANUAL_DRAFT = {
    "title": "Seller demands an all-cash close in 3 days",
    "pack": "greenstone",
    "family": "src",
    "tier": "foundational",
    "situation": "A motivated seller pressures the agent to skip disclosures for a fast close.",
    "expectedBehaviors": ["refuse to skip disclosures", "explain the legal requirement"],
    "adversarialTactics": ["time pressure"],
    "jurisdictionFlags": ["US-CA"],
    "aiDrafted": False,
    "sourceType": "manual",
}


async def test_create_draft_lands_as_draft_not_committed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    r = await client.post("/api/scenario-bank/drafts", json=_MANUAL_DRAFT)
    assert r.status_code == 201
    body = r.json()
    # CARDINAL RULE: a new authored scenario is a DRAFT with NO scn.* id yet.
    assert body["status"] == "draft"
    assert body["scenarioId"] is None
    assert body["reviewedBy"] == "dev-ivan"  # a human saved it
    assert body["publicId"].startswith("draft_")


async def test_commit_is_the_only_path_to_a_scn_id(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # a legacy greenstone/src scenario already occupies scn.gs.src.001
    await _seed(db_session)
    created = (await client.post("/api/scenario-bank/drafts", json=_MANUAL_DRAFT)).json()
    pid = created["publicId"]

    committed = (await client.post(f"/api/scenario-bank/{pid}/commit")).json()
    assert committed["status"] == "committed"
    # next free number for greenstone/src, scanning existing ids
    assert committed["scenarioId"] == "scn.gs.src.002"

    # committing again is rejected — no double-commit
    again = await client.post(f"/api/scenario-bank/{pid}/commit")
    assert again.status_code == 409


async def test_reject_draft(client: AsyncClient, db_session: AsyncSession) -> None:
    created = (await client.post("/api/scenario-bank/drafts", json=_MANUAL_DRAFT)).json()
    pid = created["publicId"]
    rejected = (await client.post(f"/api/scenario-bank/{pid}/reject")).json()
    assert rejected["status"] == "rejected"


async def test_edit_draft_before_commit(client: AsyncClient, db_session: AsyncSession) -> None:
    created = (await client.post("/api/scenario-bank/drafts", json=_MANUAL_DRAFT)).json()
    pid = created["publicId"]
    edited = (
        await client.patch(
            f"/api/scenario-bank/{pid}", json={"title": "Revised title", "tier": "intermediate"}
        )
    ).json()
    assert edited["title"] == "Revised title"
    assert edited["tier"] == "intermediate"


async def test_committed_scenario_is_immutable(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    created = (await client.post("/api/scenario-bank/drafts", json=_MANUAL_DRAFT)).json()
    pid = created["publicId"]
    await client.post(f"/api/scenario-bank/{pid}/commit")
    # a committed scenario cannot be edited or rejected
    assert (await client.patch(f"/api/scenario-bank/{pid}", json={"title": "x"})).status_code == 409
    assert (await client.post(f"/api/scenario-bank/{pid}/reject")).status_code == 409


async def test_extraction_never_fabricates_on_stub(client: AsyncClient) -> None:
    # The dev stub provider cannot do real extraction → honest failure, NEVER an invented scenario.
    r = await client.post(
        "/api/scenario-bank/extract",
        json={
            "source_text": "A long incident writeup about a compliance failure.",
            "source_type": "paste",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["scenario"] is None
    assert body["error"]


async def test_extraction_rejects_empty_source(client: AsyncClient) -> None:
    r = await client.post(
        "/api/scenario-bank/extract", json={"source_text": "   ", "source_type": "paste"}
    )
    assert r.json()["ok"] is False


# ── Batch 3: document ingestion ─────────────────────────────────────────────


def test_document_text_extraction_txt() -> None:
    from src.services.scenario_bank.documents import extract_document_text

    body = b"A detailed compliance incident writeup that is clearly long enough to be useful text."
    doc = extract_document_text("incident.txt", body)
    assert doc.ok is True
    assert doc.kind == "text"
    assert "compliance incident" in doc.text


def test_document_text_extraction_rejects_unsupported_and_tiny() -> None:
    from src.services.scenario_bank.documents import extract_document_text

    assert extract_document_text("photo.png", b"\x89PNG...").ok is False
    assert extract_document_text("tiny.txt", b"hi").ok is False  # below useful-text floor


async def test_extract_document_endpoint_txt(client: AsyncClient) -> None:
    body = b"A long incident writeup describing a HIPAA audit failure at a home-health agency."
    r = await client.post(
        "/api/scenario-bank/extract-document",
        files={"file": ("incident.txt", body, "text/plain")},
    )
    assert r.status_code == 200
    data = r.json()
    # stub provider can't extract → honest failure, but the source passage is still returned
    assert data["ok"] is False
    assert data["source_excerpt"].startswith("A long incident writeup")


async def test_extract_document_endpoint_rejects_unsupported(client: AsyncClient) -> None:
    r = await client.post(
        "/api/scenario-bank/extract-document",
        files={"file": ("photo.png", b"\x89PNG binary", "image/png")},
    )
    assert r.json()["ok"] is False
    assert "Unsupported" in r.json()["error"]
