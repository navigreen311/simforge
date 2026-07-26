"""Scenario Bank schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BankScenarioOut(BaseModel):
    """List-row view."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    publicId: str
    scenarioId: str | None = None
    title: str
    pack: str
    family: str
    tier: str
    situation: str  # included so free-text search covers it (kept short in practice)
    status: str
    aiDrafted: bool
    sourceType: str
    createdBy: str
    createdAt: datetime


class BankScenarioDetail(BankScenarioOut):
    """Full detail view (situation, behaviors, provenance, review state)."""

    expectedBehaviors: list[str]
    adversarialTactics: list[str]
    jurisdictionFlags: list[str]
    sourceRef: str | None = None
    sourceExcerpt: str | None = None
    reviewedBy: str | None = None
    reviewedAt: datetime | None = None
    version: int
    supersedesId: str | None = None
    updatedAt: datetime


class BankScenarioList(BaseModel):
    items: list[BankScenarioOut]
    total: int


# ── Batch 2: authoring / extraction / promotion request bodies ──────────────


class ExtractRequest(BaseModel):
    """Raw source text → a candidate (never saved here). The text is NOT trusted."""

    source_text: str
    source_type: str = "paste"  # paste | document | web | youtube | video
    source_ref: str | None = None


class ExtractResponse(BaseModel):
    ok: bool
    error: str | None = None
    confidence: float | None = None
    scenario: dict | None = None  # the editable candidate (pre-fills the human review form)
    source_excerpt: str | None = None  # the source passage, attached as provenance on save
    source_ref: str | None = None  # e.g. the uploaded filename


class DraftRequest(BaseModel):
    """Save a human-approved DRAFT. Used by both manual authoring and extraction-approval."""

    title: str
    pack: str
    family: str
    tier: str
    situation: str
    expectedBehaviors: list[str] = []
    adversarialTactics: list[str] = []
    jurisdictionFlags: list[str] = []
    aiDrafted: bool = False
    sourceType: str = "manual"
    sourceRef: str | None = None
    sourceExcerpt: str | None = None


class DraftEditRequest(BaseModel):
    """Edit a non-committed draft's content (the review edit). All fields optional."""

    title: str | None = None
    pack: str | None = None
    family: str | None = None
    tier: str | None = None
    situation: str | None = None
    expectedBehaviors: list[str] | None = None
    adversarialTactics: list[str] | None = None
    jurisdictionFlags: list[str] | None = None


class VocabularyOut(BaseModel):
    """The fixed vocabularies the authoring UI must present (no free-text taxonomy)."""

    packs: list[str]
    families: list[str]
    tiers: list[str]


# ── Batch 5: web-search ingestion ───────────────────────────────────────────


class WebSearchRequest(BaseModel):
    query: str
    max_results: int | None = None


class WebSearchResultOut(BaseModel):
    title: str
    url: str
    snippet: str
    content: str  # extraction-ready text (fed to /extract as source_text)
    content_chars: int
    score: float | None = None
    published_date: str | None = None


class WebSearchResponse(BaseModel):
    """Search results, or an honest not-configured / error state (never fabricated results)."""

    available: bool  # is a real provider configured?
    provider: str
    query: str
    results: list[WebSearchResultOut] = []
    error: str | None = None


class WebSearchStatus(BaseModel):
    available: bool
    provider: str
