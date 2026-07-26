"""Pack + Scenario response/request schemas (blueprint §C.3.4/§C.3.5)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScenarioSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scenarioId: str
    title: str
    tier: str
    testedAgentVillageId: str
    sloSeconds: int
    isGolden: bool


class PackSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    packId: str
    name: str
    version: str
    ownerVenture: str
    phiRequired: bool
    executionModeDefault: str
    locale: str = "en"
    signedBy: str | None = None
    signedAt: datetime | None = None


class PackCard(PackSummary):
    """List-row view enriched for the readable Packs page (Part A). Superset of PackSummary."""

    complianceFlags: list[str]
    scenarioCount: int
    tierCounts: dict[str, int]  # {foundational, intermediate, advanced_crisis}
    goldenCount: int


class PackDetail(PackSummary):
    complianceFlags: list[str]
    rubricProfile: str
    scenarios: list[ScenarioSummary]


class PackList(BaseModel):
    items: list[PackCard]
    total: int


class FlagInfoOut(BaseModel):
    label: str
    tooltip: str
    phi: bool
    jurisdiction: str | None = None


class FlagCatalogOut(BaseModel):
    """Plain-language labels for every flag that can appear on a pack chip, + legend copy."""

    flags: dict[str, FlagInfoOut]
    legend: dict[str, str]


class IngestPackRequest(BaseModel):
    pack_dir: str  # path under packs/, e.g. "greenstone/v1"


class ValidationIssueOut(BaseModel):
    severity: str
    code: str
    message: str
    location: str = ""


class IngestPackResponse(BaseModel):
    ok: bool
    pack_id: str
    scenarios: int
    issues: list[ValidationIssueOut]


class SignPackRequest(BaseModel):
    signed_by: str
