"""Scenario YAML schema (blueprint §B.1 Scenario)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from validator.pack_schema import TIERS


class ScenarioSpec(BaseModel):
    scenario_id: str = Field(..., pattern=r"^scn\.[a-z0-9_.]+$")
    title: str
    tier: str
    tested_agent_village_id: str
    tested_forge_caps: list[str] = Field(default_factory=list)
    training_domains: list[str] = Field(default_factory=list)
    seed: int = 0
    slo_seconds: int = Field(..., gt=0)
    compliance_checks: list[str] = Field(default_factory=list)
    cold_open: str
    is_golden: bool = False

    @field_validator("tier")
    @classmethod
    def _tier(cls, v: str) -> str:
        if v not in TIERS:
            raise ValueError(f"tier must be one of {TIERS}")
        return v
