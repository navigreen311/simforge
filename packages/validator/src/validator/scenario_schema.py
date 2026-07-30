"""Scenario YAML schema (spec §6.2 Scenario)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from validator.pack_schema import TIERS

# Canonical training-domain vocabulary (spec §6.3 rule `training_domains_canonical`).
CANONICAL_TRAINING_DOMAINS = (
    "customer_relations",
    "voice",
    "enrollments_onboarding",
    "document_handling",
    "financing_mock_bank",
    "end_to_end_workflow",
    "crisis_adverse_event",
)


class ScenarioSetup(BaseModel):
    """Mock-world + forge-sandbox seed state (spec §6.2 setup). Refs resolve to pack fixtures."""

    personas: list[dict] = Field(
        default_factory=list
    )  # [{ref: "persona.seller.distressed_mf_001"}]
    documents: list[dict] = Field(default_factory=list)
    properties: list[dict] = Field(default_factory=list)
    forge_sandbox_state: dict = Field(default_factory=dict)


class Complication(BaseModel):
    id: str
    trigger: str
    effect: str


class ExpectedOutcome(BaseModel):
    state_changes: list[str] = Field(default_factory=list)
    forbidden_state_changes: list[str] = Field(default_factory=list)


class CognitiveExpectations(BaseModel):
    breath_coherence_min: float | None = None
    soul_stability_min: float | None = None
    fot_pressure_ceiling: str | None = None
    arc_no_fragmentation: bool | None = None
    echo_regret_delta_max: float | None = None
    hfm_drive_deficit_max: float | None = None
    ame_reputation_decline_max: float | None = None


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
    # --- spec §6.2 fields (optional; the thin v1 corpus omits them) ---
    stage: str | None = None  # role×stage coverage taxonomy (sourcing/underwriting/…)
    setup: ScenarioSetup | None = None
    complications: list[Complication] = Field(default_factory=list)
    expected_outcome: ExpectedOutcome | None = None
    cognitive_expectations: CognitiveExpectations | None = None
    handoff_chain: list[str] = Field(default_factory=list)
    expected_escalation: str | None = None
    blind_mode: bool | None = None  # per-scenario blind-mode override

    @field_validator("tier")
    @classmethod
    def _tier(cls, v: str) -> str:
        if v not in TIERS:
            raise ValueError(f"tier must be one of {TIERS}")
        return v

    @property
    def persona_refs(self) -> list[str]:
        return [str(p.get("ref", "")) for p in (self.setup.personas if self.setup else [])]

    def fixture_refs(self) -> list[tuple[str, str]]:
        """(kind, ref) for every fixture the scenario references in setup."""
        refs: list[tuple[str, str]] = []
        if not self.setup:
            return refs
        for p in self.setup.personas:
            refs.append(("persona", str(p.get("ref", ""))))
        for d in self.setup.documents:
            refs.append(("document", str(d.get("ref", ""))))
        for pr in self.setup.properties:
            refs.append(("property", str(pr.get("ref", ""))))
        return refs
