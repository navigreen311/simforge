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
