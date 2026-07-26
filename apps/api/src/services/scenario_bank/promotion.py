"""Two-stage human promotion for bank scenarios (Batch 1/2).

    AI draft (aiDrafted=true) → human-approved draft (status=draft, reviewedBy set) → committed.

`create_draft` always sets ``reviewedBy`` (the human who saved it — an author for manual, an
approver for an AI extraction). `commit_draft` is the SECOND, explicit human action: it assigns a
real ``scn.*`` id, flips status to ``committed``, and records provenance in Lineage. Nothing here is
automatic — there is no code path that commits without a human calling commit.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from src.models.bank_scenario import BankScenario
from src.models.pack import Scenario
from src.services.registry.lineage import add_edge
from src.services.venture.registry import scenario_code_for
from src.utils.time import utcnow


class PromotionError(Exception):
    """A promotion action was invalid (e.g. committing an already-committed scenario)."""


async def next_scenario_id(session: AsyncSession, pack: str, family: str) -> str:
    """The next free scn.{code}.{family}.{nnn}, scanning BOTH the bank and the runtime table.

    The scenario-code prefix comes from the Venture Registry (was a hardcoded map).
    """
    code = await scenario_code_for(session, pack)
    prefix = f"scn.{code}.{family}."
    like = f"{prefix}%"
    bank_ids = (
        (
            await session.execute(
                select(BankScenario.scenarioId).where(BankScenario.scenarioId.like(like))
            )
        )
        .scalars()
        .all()
    )
    run_ids = (
        (await session.execute(select(Scenario.scenarioId).where(Scenario.scenarioId.like(like))))
        .scalars()
        .all()
    )
    max_n = 0
    for sid in [*bank_ids, *run_ids]:
        m = re.search(rf"^{re.escape(prefix)}(\d+)$", sid or "")
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"{prefix}{max_n + 1:03d}"


async def create_draft(
    session: AsyncSession,
    *,
    title: str,
    pack: str,
    family: str,
    tier: str,
    situation: str,
    expected_behaviors: list[str],
    adversarial_tactics: list[str],
    jurisdiction_flags: list[str],
    created_by: str,
    ai_drafted: bool,
    source_type: str,
    source_ref: str | None = None,
    source_excerpt: str | None = None,
) -> BankScenario:
    """Save a human-approved DRAFT (never committed). reviewedBy = the human who saved it."""
    now = utcnow()
    draft = BankScenario(
        publicId=f"draft_{ULID()}",
        scenarioId=None,
        title=title.strip(),
        pack=pack,
        family=family,
        tier=tier,
        situation=situation.strip(),
        expectedBehaviors=expected_behaviors,
        adversarialTactics=adversarial_tactics,
        jurisdictionFlags=jurisdiction_flags,
        status="draft",
        aiDrafted=ai_drafted,
        sourceType=source_type,
        sourceRef=source_ref,
        sourceExcerpt=source_excerpt,
        createdBy=created_by,
        reviewedBy=created_by,  # a human saved/approved this draft
        reviewedAt=now,
        version=1,
    )
    session.add(draft)
    await session.commit()
    await session.refresh(draft)
    return draft


async def commit_draft(session: AsyncSession, public_id: str, actor: str) -> BankScenario:
    """The explicit human commit: draft → committed, assign a scn.* id, record provenance."""
    draft = (
        await session.execute(select(BankScenario).where(BankScenario.publicId == public_id))
    ).scalar_one_or_none()
    if draft is None:
        raise PromotionError(f"Scenario not found: {public_id}")
    if draft.status not in ("draft", "in_review"):
        raise PromotionError(f"Only a draft can be committed (status is '{draft.status}').")

    scenario_id = await next_scenario_id(session, draft.pack, draft.family)
    draft.scenarioId = scenario_id
    draft.status = "committed"
    draft.reviewedBy = actor
    draft.reviewedAt = utcnow()

    # Provenance edge: the committed scenario derives from its source (feeds Lineage).
    source_urn = (
        f"urn:gc:village:source:{draft.sourceType}:{draft.sourceRef}"
        if draft.sourceRef
        else f"urn:gc:village:source:{draft.sourceType}"
    )
    await add_edge(
        session,
        from_urn=f"urn:gc:village:scenario:{scenario_id}",
        to_urn=source_urn,
        relation_type="derived_from",
        metadata={"bank_public_id": draft.publicId, "committed_by": actor},
    )
    await session.commit()
    await session.refresh(draft)
    return draft


async def reject_draft(session: AsyncSession, public_id: str, actor: str) -> BankScenario:
    draft = (
        await session.execute(select(BankScenario).where(BankScenario.publicId == public_id))
    ).scalar_one_or_none()
    if draft is None:
        raise PromotionError(f"Scenario not found: {public_id}")
    if draft.status == "committed":
        raise PromotionError("A committed scenario cannot be rejected (archive it instead).")
    draft.status = "rejected"
    draft.reviewedBy = actor
    draft.reviewedAt = utcnow()
    await session.commit()
    await session.refresh(draft)
    return draft


async def edit_draft(session: AsyncSession, public_id: str, fields: dict) -> BankScenario:
    """Edit a non-committed draft's content fields (the human review edit)."""
    draft = (
        await session.execute(select(BankScenario).where(BankScenario.publicId == public_id))
    ).scalar_one_or_none()
    if draft is None:
        raise PromotionError(f"Scenario not found: {public_id}")
    if draft.status == "committed":
        raise PromotionError("A committed scenario is immutable — create a new version instead.")
    editable = {
        "title",
        "pack",
        "family",
        "tier",
        "situation",
        "expectedBehaviors",
        "adversarialTactics",
        "jurisdictionFlags",
    }
    for k, v in fields.items():
        if k in editable and v is not None:
            setattr(draft, k, v)
    await session.commit()
    await session.refresh(draft)
    return draft
