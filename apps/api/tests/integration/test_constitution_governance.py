"""Constitution §11.6: articles, quorum-gated ratify, meta-amendment (14d + unanimous)."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.governance import ConstitutionalAmendment
from src.services.governance import ratify_constitution
from src.services.governance.amendment import AmendmentError, propose_amendment, ratify_amendment
from src.services.governance.constitution import parse_articles

_YAML = (
    "preamble: gov\n"
    "articles:\n"
    "  - id: A1\n    title: Evidence-bound\n    text: No pass no cert.\n"
    "  - id: A5\n    title: Amendment requires cooling and quorum\n    text: cooling + quorum.\n"
)


def test_parse_articles() -> None:
    arts = parse_articles(_YAML)
    assert [a["id"] for a in arts] == ["A1", "A5"]
    assert arts[1]["title"].startswith("Amendment")


async def test_articles_endpoint(client: AsyncClient, db_session: AsyncSession) -> None:
    await ratify_constitution(db_session, "v1.0.0", "ivan", _YAML)
    await db_session.commit()
    body = (await client.get("/api/constitution/articles")).json()
    assert body["amendment_process_article"] == "A5"
    assert {a["id"] for a in body["articles"]} == {"A1", "A5"}


async def test_quorum_gated_amendment_blocks_ratify_until_approved(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await ratify_constitution(db_session, "v1.0.0", "ivan", _YAML)
    await db_session.commit()
    # An amendment with declared approvers → ratification is quorum-gated.
    amend = await propose_amendment(
        db_session,
        "ivan",
        "diff: x",
        cooling_days=0,
        target_article="A1",
        required_approvers=["ivan", "reviewer"],
        quorum_rule="two_of_three",
    )
    approval_id = amend.impactAnalysis["approval_request_id"]
    assert approval_id

    # Cooling has ended but quorum not met → ratify blocked.
    try:
        await ratify_amendment(db_session, amend.amendmentId, "ivan")
        raise AssertionError("expected quorum block")
    except AmendmentError as exc:
        assert "quorum" in str(exc).lower()

    # Two approvals resolve the request → ratify now succeeds.
    await client.post(
        f"/api/approvals/{approval_id}/vote", json={"approver": "ivan", "decision": "approve"}
    )
    await client.post(
        f"/api/approvals/{approval_id}/vote", json={"approver": "reviewer", "decision": "approve"}
    )
    result = await ratify_amendment(db_session, amend.amendmentId, "ivan")
    assert result["new_version"] == "v1.0.1"


async def test_meta_amendment_forces_14d_unanimous_and_two_approvers(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await ratify_constitution(db_session, "v1.0.0", "ivan", _YAML)
    await db_session.commit()
    # Amending A5 (the amendment process) with <2 approvers is rejected.
    try:
        await propose_amendment(
            db_session, "ivan", "diff: x", target_article="A5", required_approvers=["ivan"]
        )
        raise AssertionError("expected meta-amendment approver requirement")
    except AmendmentError as exc:
        assert "meta-amendment" in str(exc).lower()

    # With founder + witness it is accepted, forced to unanimous + 14-day cooling.
    amend = await propose_amendment(
        db_session,
        "ivan",
        "diff: x",
        target_article="A5",
        required_approvers=["ivan", "witness"],
    )
    assert amend.impactAnalysis["is_meta"] is True
    assert amend.impactAnalysis["quorum_rule"] == "unanimous"
    # Cooling window is ≥14 days out.
    row = (
        await db_session.execute(
            select(ConstitutionalAmendment).where(
                ConstitutionalAmendment.amendmentId == amend.amendmentId
            )
        )
    ).scalar_one()
    assert (row.coolingPeriodEndsAt - row.proposedAt).days >= 14


async def test_legacy_no_approver_amendment_still_cooling_only(
    db_session: AsyncSession,
) -> None:
    # Back-compat: an amendment with no declared approvers ratifies on cooling alone.
    await ratify_constitution(db_session, "v1.0.0", "ivan", _YAML)
    await db_session.commit()
    amend = await propose_amendment(db_session, "ivan", "diff: y", cooling_days=0)
    assert "approval_request_id" not in (amend.impactAnalysis or {})
    result = await ratify_amendment(db_session, amend.amendmentId, "ivan")
    assert result["new_version"] == "v1.0.1"
