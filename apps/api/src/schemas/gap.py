"""Gap schemas (blueprint §C.3.9)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SummaryPlain(BaseModel):
    """Deterministic operator-readable description of a Forge fault (fault catalog)."""

    code: str | None = None
    what: str
    why: str
    action: str


class SoftwareGapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticketId: str
    forge: str
    module: str
    severity: str
    summary: str  # kept for backward compatibility (raw machine string)
    summary_technical: str = ""  # the raw machine string, explicitly named for engineers
    summary_plain: SummaryPlain | None = None  # plain-language {what, why, action} from the catalog
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
