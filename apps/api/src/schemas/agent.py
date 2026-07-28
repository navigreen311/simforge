"""Agent schemas (blueprint §C.3.2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AgentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    villageAgentId: str
    name: str
    role: str
    departmentId: str
    currentAutonomyLevel: str
    gardnerFlag: bool
    level10Enabled: bool


class AgentList(BaseModel):
    items: list[AgentSummary]
    total: int
    page: int
    page_size: int


class LadderLevelOut(BaseModel):
    level: str
    index: int
    meaning: str
    is_floor: bool


class FlagInfoOut(BaseModel):
    key: str
    label: str
    meaning: str
    defined: bool  # is there a formal in-app policy definition for this flag?


class AgentsLegendOut(BaseModel):
    """Plain-language reference for the Agents page: the autonomy ladder + the flag vocabulary."""

    floor: str
    levels: list[LadderLevelOut]
    flags: list[FlagInfoOut]


# ── Add agents (single + bulk) ──────────────────────────────────────────────
# New agents ALWAYS start at floor autonomy with zero certs — there is no autonomy field here, so
# "add agent" can never be a backdoor around the certification gate.


class AgentCreateRequest(BaseModel):
    name: str
    villageAgentId: str | None = None  # auto-generated from name if blank
    role: str = ""
    departmentId: str
    gardnerFlag: bool = False
    level10Enabled: bool = False


class BulkAgentRow(BaseModel):
    name: str = ""
    id: str = ""
    role: str = ""
    department: str = ""  # matched by department id, villageKey, or name
    flags: str = ""  # free text, e.g. "gardner;l10"


class BulkImportRequest(BaseModel):
    rows: list[BulkAgentRow]


class BulkRowResult(BaseModel):
    index: int
    name: str
    villageAgentId: str | None = None
    status: str  # imported | skipped | error
    reason: str | None = None


class BulkImportResponse(BaseModel):
    imported: int
    skipped: int
    errored: int
    results: list[BulkRowResult]
