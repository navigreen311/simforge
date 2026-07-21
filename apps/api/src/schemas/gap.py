"""Gap schemas (blueprint §C.3.9)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SoftwareGapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticketId: str
    forge: str
    module: str
    severity: str
    summary: str
    detail: str
    proposedFix: str | None = None
    status: str
    occurrenceCount: int
    linearUrl: str | None = None


class VillageOSGapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticketId: str
    framework: str
    severity: str
    summary: str
    detail: str
    proposedFix: str | None = None
    status: str
    occurrenceCount: int


class SoftwareGapList(BaseModel):
    items: list[SoftwareGapOut]
    total: int


class VillageOSGapList(BaseModel):
    items: list[VillageOSGapOut]
    total: int


class UpdateGapStatusRequest(BaseModel):
    status: str  # open | triaged | in_progress | fixed | wontfix
