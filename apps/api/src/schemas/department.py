"""Department schemas (blueprint §C.3.3)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DepartmentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    villageKey: str
    name: str
    totalAgents: int


class DepartmentList(BaseModel):
    items: list[DepartmentSummary]
    total: int
