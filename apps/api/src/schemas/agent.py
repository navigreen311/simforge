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
