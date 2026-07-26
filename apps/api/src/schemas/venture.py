"""Venture registry schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VentureOut(BaseModel):
    """List-row view (with computed counts)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    description: str
    status: str
    scenarioCode: str
    defaultComplianceFlags: list[str]
    internalForges: list[str]
    capabilities: list[str]
    createdBy: str
    createdAt: datetime
    packCount: int = 0
    committedScenarioCount: int = 0  # committed bank scenarios tagged to this venture
    capabilityCount: int = 0


class VenturePackRef(BaseModel):
    packId: str
    name: str
    version: str
    scenarioCount: int


class SpecDocumentRef(BaseModel):
    id: str
    filename: str
    uploadedAt: datetime
    proposalsCount: int
    scenariosCount: int


class VentureDetail(VentureOut):
    packs: list[VenturePackRef]
    specDocuments: list[SpecDocumentRef] = []


class VentureList(BaseModel):
    items: list[VentureOut]
    total: int


class VentureCreateRequest(BaseModel):
    name: str
    slug: str
    description: str = ""
    status: str = "in_development"
    scenarioCode: str | None = None  # auto-derived from slug if omitted
    defaultComplianceFlags: list[str] = []
    internalForges: list[str] = []
    capabilities: list[str] = []


class VentureUpdateRequest(BaseModel):
    """Partial update of venture metadata (used to apply reviewed spec enrichment, Part B)."""

    name: str | None = None
    description: str | None = None
    status: str | None = None
    defaultComplianceFlags: list[str] | None = None
    internalForges: list[str] | None = None
    capabilities: list[str] | None = None


# ── Part B: spec upload ──────────────────────────────────────────────────────


class EnrichmentProposalOut(BaseModel):
    """Pass-1 proposed venture metadata (a diff for human review — never auto-applied)."""

    description: str
    complianceFlags: list[str]
    internalForges: list[str]
    capabilities: list[str]
    confidence: float | None = None


class ProducedScenarioOut(BaseModel):
    publicId: str
    title: str
    tier: str


class SpecUploadResponse(BaseModel):
    """What a spec upload produced. Both passes are proposals/drafts; nothing is applied."""

    ok: bool
    error: str | None = None
    specDocumentId: str | None = None
    filename: str | None = None
    enrichment: EnrichmentProposalOut | None = None  # review as a diff, then apply via PATCH
    produced_scenarios: list[ProducedScenarioOut] = []  # AI-drafts routed to the bank (unreviewed)
