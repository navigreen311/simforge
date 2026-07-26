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
