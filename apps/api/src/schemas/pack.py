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
    signedBy: str | None = None
    signedAt: datetime | None = None


class PackDetail(PackSummary):
    complianceFlags: list[str]
    rubricProfile: str
    scenarios: list[ScenarioSummary]


class PackList(BaseModel):
    items: list[PackSummary]
    total: int


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
