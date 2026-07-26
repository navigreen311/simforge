"""Scenario Bank router — browse / search / filter the reviewable scenario library (Batch 1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dev import Principal, get_current_principal
from src.config import settings
from src.db import get_session
from src.deps import require_role
from src.models.bank_scenario import BankScenario
from src.schemas.bank_scenario import (
    BankScenarioDetail,
    BankScenarioList,
    BankScenarioOut,
    DraftEditRequest,
    DraftRequest,
    ExtractRequest,
    ExtractResponse,
    VocabularyOut,
    WebSearchRequest,
    WebSearchResponse,
    WebSearchResultOut,
    WebSearchStatus,
)
from src.services.scenario_bank import (
    PromotionError,
    commit_draft,
    create_draft,
    extract_scenario,
    reject_draft,
)
from src.services.scenario_bank.documents import extract_document_text
from src.services.scenario_bank.extraction import FAMILIES, PACKS, TIERS
from src.services.scenario_bank.promotion import edit_draft
from src.services.scenario_bank.web_search import (
    WebSearchUnavailable,
    resolve_web_search_provider,
    search_web,
    web_search_available,
)

_EXCERPT_CHARS = 2000  # how much source text to retain as provenance on the draft

router = APIRouter()


@router.get("/", response_model=BankScenarioList, dependencies=[Depends(require_role("viewer"))])
async def list_bank_scenarios(
    session: AsyncSession = Depends(get_session),
    status_filter: str | None = Query(default=None, alias="status"),
    pack: str | None = Query(default=None),
    family: str | None = Query(default=None),
    tier: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    ai_drafted: bool | None = Query(default=None),
    search: str | None = Query(default=None, description="Match title / situation / id"),
) -> BankScenarioList:
    def _apply(stmt):  # noqa: ANN001, ANN202 — SQLAlchemy Select, verbose to spell
        if status_filter:
            stmt = stmt.where(BankScenario.status == status_filter)
        if pack:
            stmt = stmt.where(BankScenario.pack == pack)
        if family:
            stmt = stmt.where(BankScenario.family == family)
        if tier:
            stmt = stmt.where(BankScenario.tier == tier)
        if source_type:
            stmt = stmt.where(BankScenario.sourceType == source_type)
        if ai_drafted is not None:
            stmt = stmt.where(BankScenario.aiDrafted == ai_drafted)
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(BankScenario.title).like(like),
                    func.lower(BankScenario.situation).like(like),
                    func.lower(BankScenario.publicId).like(like),
                    func.lower(func.coalesce(BankScenario.scenarioId, "")).like(like),
                )
            )
        return stmt

    total = (
        await session.execute(_apply(select(func.count()).select_from(BankScenario)))
    ).scalar_one()
    rows = (
        (
            await session.execute(
                _apply(select(BankScenario)).order_by(BankScenario.createdAt.desc())
            )
        )
        .scalars()
        .all()
    )
    return BankScenarioList(items=[BankScenarioOut.model_validate(r) for r in rows], total=total)


@router.get("/counts", dependencies=[Depends(require_role("viewer"))])
async def bank_counts(session: AsyncSession = Depends(get_session)) -> dict:
    """Per-status counts + the human review queue size (drafts + in_review awaiting a human)."""
    rows = (
        await session.execute(
            select(BankScenario.status, func.count()).group_by(BankScenario.status)
        )
    ).all()
    by_status = {s: n for s, n in rows}
    awaiting_review = by_status.get("draft", 0) + by_status.get("in_review", 0)
    return {
        "by_status": by_status,
        "total": sum(by_status.values()),
        "awaiting_review": awaiting_review,
    }


@router.get(
    "/vocabulary",
    response_model=VocabularyOut,
    dependencies=[Depends(require_role("viewer"))],
)
async def get_vocabulary() -> VocabularyOut:
    """The fixed pack/family/tier vocabularies the authoring & extraction UI must use."""
    return VocabularyOut(packs=list(PACKS), families=list(FAMILIES), tiers=list(TIERS))


@router.get(
    "/web-search/status",
    response_model=WebSearchStatus,
    dependencies=[Depends(require_role("viewer"))],
)
async def web_search_status() -> WebSearchStatus:
    """Whether live web-search ingestion is configured (drives the UI's honest empty state)."""
    return WebSearchStatus(
        available=web_search_available(),
        provider=resolve_web_search_provider(settings.web_search_provider),
    )


@router.get(
    "/{public_id}",
    response_model=BankScenarioDetail,
    dependencies=[Depends(require_role("viewer"))],
)
async def get_bank_scenario(
    public_id: str, session: AsyncSession = Depends(get_session)
) -> BankScenarioDetail:
    row = (
        await session.execute(select(BankScenario).where(BankScenario.publicId == public_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    return BankScenarioDetail.model_validate(row)


# ─────────────────────────────────────────────────────────────────────────────
# Ingestion + two-stage human promotion (Batch 2).
#
# CARDINAL RULE: nothing here auto-commits. `extract` only proposes a candidate; `drafts` saves a
# human-approved DRAFT; only `commit` (a separate, explicit human action) assigns a scn.* id and
# lets a scenario into the active bank. Extraction never fabricates — a stub/blank result is an
# honest error, not an invented scenario.
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/extract", response_model=ExtractResponse, dependencies=[Depends(require_role("pack_owner"))]
)
async def extract(body: ExtractRequest) -> ExtractResponse:
    """Propose a candidate scenario from raw text. Saves NOTHING — the caller reviews it first."""
    result = await extract_scenario(body.source_text)
    excerpt = body.source_text.strip()[:_EXCERPT_CHARS]
    if not result.ok:
        return ExtractResponse(ok=False, error=result.error)
    return ExtractResponse(
        ok=True,
        confidence=result.confidence,
        scenario=result.scenario,
        source_excerpt=excerpt,
        source_ref=body.source_ref,
    )


@router.post(
    "/extract-document",
    response_model=ExtractResponse,
    dependencies=[Depends(require_role("pack_owner"))],
)
async def extract_from_document(file: UploadFile = File(...)) -> ExtractResponse:  # noqa: B008
    """Upload a PDF/DOCX/TXT/MD → extract text → propose a candidate. Saves NOTHING.

    Two honest-failure gates before any LLM call: an unreadable/empty/oversized/scanned file returns
    a plain error and no scenario (no OCR, no fabrication).
    """
    data = await file.read()
    doc = extract_document_text(file.filename or "upload", data)
    if not doc.ok:
        return ExtractResponse(ok=False, error=doc.error)
    result = await extract_scenario(doc.text)
    excerpt = doc.text.strip()[:_EXCERPT_CHARS]
    if not result.ok:
        return ExtractResponse(ok=False, error=result.error, source_excerpt=excerpt)
    return ExtractResponse(
        ok=True,
        confidence=result.confidence,
        scenario=result.scenario,
        source_excerpt=excerpt,
        source_ref=file.filename,
    )


@router.post(
    "/web-search",
    response_model=WebSearchResponse,
    dependencies=[Depends(require_role("pack_owner"))],
)
async def web_search(body: WebSearchRequest) -> WebSearchResponse:
    """Find real-world sources for a query. Returns extraction-ready text — creates NOTHING.

    Each result's `content` feeds the existing /extract path, so a chosen result becomes an
    AI-drafted candidate the user reviews and (separately) commits. If no provider is configured,
    returns `available=false` with an honest message — never fabricated results.
    """
    provider = resolve_web_search_provider(settings.web_search_provider)
    if not body.query.strip():
        return WebSearchResponse(
            available=web_search_available(), provider=provider, query="", error="Query is empty."
        )
    try:
        results = await search_web(body.query, body.max_results)
    except WebSearchUnavailable as exc:
        return WebSearchResponse(
            available=False, provider=provider, query=body.query, error=str(exc)
        )
    except Exception as exc:  # noqa: BLE001 — surface a provider/network error honestly
        return WebSearchResponse(
            available=True,
            provider=provider,
            query=body.query,
            error=f"Web search failed: {exc}",
        )
    return WebSearchResponse(
        available=True,
        provider=provider,
        query=body.query,
        results=[
            WebSearchResultOut(
                title=r.title,
                url=r.url,
                snippet=r.snippet,
                content=r.content,
                content_chars=len(r.content),
                score=r.score,
                published_date=r.published_date,
            )
            for r in results
        ],
    )


@router.post(
    "/drafts",
    response_model=BankScenarioDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("pack_owner"))],
)
async def create_bank_draft(
    body: DraftRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> BankScenarioDetail:
    """Save a human-approved DRAFT (manual authoring or an approved extraction). Never committed."""
    draft = await create_draft(
        session,
        title=body.title,
        pack=body.pack,
        family=body.family,
        tier=body.tier,
        situation=body.situation,
        expected_behaviors=body.expectedBehaviors,
        adversarial_tactics=body.adversarialTactics,
        jurisdiction_flags=body.jurisdictionFlags,
        created_by=principal.subject,
        ai_drafted=body.aiDrafted,
        source_type=body.sourceType,
        source_ref=body.sourceRef,
        source_excerpt=body.sourceExcerpt,
    )
    return BankScenarioDetail.model_validate(draft)


@router.patch(
    "/{public_id}",
    response_model=BankScenarioDetail,
    dependencies=[Depends(require_role("pack_owner"))],
)
async def edit_bank_draft(
    public_id: str,
    body: DraftEditRequest,
    session: AsyncSession = Depends(get_session),
) -> BankScenarioDetail:
    """Edit a non-committed draft's content (the review edit)."""
    try:
        draft = await edit_draft(session, public_id, body.model_dump(exclude_unset=True))
    except PromotionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return BankScenarioDetail.model_validate(draft)


@router.post(
    "/{public_id}/commit",
    response_model=BankScenarioDetail,
    dependencies=[Depends(require_role("pack_owner"))],
)
async def commit_bank_draft(
    public_id: str,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> BankScenarioDetail:
    """The explicit human commit: draft → committed, assigns a scn.* id, records provenance."""
    try:
        committed = await commit_draft(session, public_id, principal.subject)
    except PromotionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return BankScenarioDetail.model_validate(committed)


@router.post(
    "/{public_id}/reject",
    response_model=BankScenarioDetail,
    dependencies=[Depends(require_role("pack_owner"))],
)
async def reject_bank_draft(
    public_id: str,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> BankScenarioDetail:
    try:
        rejected = await reject_draft(session, public_id, principal.subject)
    except PromotionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return BankScenarioDetail.model_validate(rejected)
