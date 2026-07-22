"""Pack YAML schema (blueprint §B.1 Pack + §C.3.4)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

TIERS = ("foundational", "intermediate", "advanced_crisis")
EXECUTION_MODES = ("sandbox", "integrated")
NARRATIVE_MODES = ("protected", "integrated")
# Locales with a translated rubric-prompt set (blueprint §L.4 locale Packs; ADR-0041).
LOCALES = ("en", "es")


class ReadinessGateSpec(BaseModel):
    tier_thresholds: dict[str, float] = Field(
        default_factory=lambda: {"F": 0.70, "I": 0.80, "AC": 0.85}
    )
    cognitive_aggregate_min: float = 0.75
    blind_mode_pct: float = 0.25
    arc_fragmentation_auto_fail: bool = True
    compliance_require_pass: bool = True


class PackSpec(BaseModel):
    pack_id: str = Field(..., pattern=r"^pack\.[a-z0-9_-]+\.v\d+$")
    name: str
    version: str
    owner_venture: str
    owner_human: str
    phi_required: bool = False
    compliance_flags: list[str] = Field(default_factory=list)
    integrated_runs_allowed: bool = False
    execution_mode_default: str = "sandbox"
    narrative_mode_default: str = "protected"
    locale: str = "en"
    rubric_profile: str
    readiness_gate: ReadinessGateSpec = Field(default_factory=ReadinessGateSpec)

    @field_validator("locale")
    @classmethod
    def _locale(cls, v: str) -> str:
        if v not in LOCALES:
            raise ValueError(f"locale must be one of {LOCALES}")
        return v

    @field_validator("execution_mode_default")
    @classmethod
    def _exec_mode(cls, v: str) -> str:
        if v not in EXECUTION_MODES:
            raise ValueError(f"execution_mode_default must be one of {EXECUTION_MODES}")
        return v

    @field_validator("narrative_mode_default")
    @classmethod
    def _narr_mode(cls, v: str) -> str:
        if v not in NARRATIVE_MODES:
            raise ValueError(f"narrative_mode_default must be one of {NARRATIVE_MODES}")
        return v
