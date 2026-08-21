"""Forge Operation Certification payload contracts (Batch 4, Rev 2 shapes).

Inbound  (Office → SimForge): `ForgeOperationCurriculum` — curriculum + instruction set + coverage.
Inbound  (run → SimForge):    `GateResultRequest` — the raw outcome of an operation battery.
Outbound (SimForge → Office): `ForgeOperationResults` — the gate-result callback shape.

Hard contract rules baked into these shapes:
  - `operation_rubric_version` is a SEPARATE, required field — never the domain rubric_version.
  - `instruction_content_hash` is ECHOED on the outbound; a run whose hash != the Office-declared
    hash VOIDS the cert (handled in services/operation/recert.py — never softened to a warning).
  - `operation_rubric_results` is a NAMED LIST of {dimension, verdict, score?, threshold?} — NOT
    fixed dimension columns, so the rubric can finalize/extend without breaking the contract.
  - every Unit A result carries the DENOMINATOR: functions_certified of functions_in_module.
  - `rubric_dimension_spread` is required on every Unit A result (the collapse check).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# =================================================================================================
# Inbound — curriculum submission (Office → SimForge)
# =================================================================================================


class InstructionSetRef(BaseModel):
    forge_id: str
    module_id: str
    instruction_version: str  # semver
    forge_api_version: str  # semver
    content_hash: str  # the cert BINDS to this; a run mismatch VOIDS
    authored_by: str | None = None


class CertificationUnitRequest(BaseModel):
    unit_type: str  # "agent_operation" | "department_context"
    forge_id: str
    # Unit A
    agent_id: str | None = None
    module_id: str | None = None
    # Unit B (context)
    department_id: str | None = None
    forge_context: str | None = None
    venture_context: str | None = None


class OperationScenarioSubmission(BaseModel):
    scenario_class: str  # one of ScenarioClass
    module_id: str
    instruction_section: str  # which section of the instruction set it tests
    expected_behavior: str
    expected_escalation: str
    never_do_entry: str | None = None  # for never_do_violation scenarios


class CoverageDeclaration(BaseModel):
    modules_in_forge: int
    modules_covered: int
    modules_uncovered: list[str] = Field(default_factory=list)  # NAMED, honest denominator
    functions_in_module: int
    functions_covered: int


class ForgeOperationCurriculum(BaseModel):
    instruction_set_ref: InstructionSetRef
    certification_units_requested: list[CertificationUnitRequest]
    operation_scenarios: list[OperationScenarioSubmission]
    coverage_declaration: CoverageDeclaration
    # The module's never-do list per module (from the instruction set). Each entry needs a
    # never_do_violation scenario proving the agent declines (validated at submission).
    module_never_do: dict[str, list[str]] = Field(default_factory=dict)


# =================================================================================================
# Named-list rubric result item (shared inbound/outbound)
# =================================================================================================


class OperationRubricResultItem(BaseModel):
    """One dimension's result — a NAMED entry, never a fixed column. `not_applicable` is a
    first-class verdict; a not_applicable dimension carries NO score (it is not a zero)."""

    dimension: str
    verdict: str  # PASS | FAIL | NOT_RUN | not_applicable
    score: float | None = None
    threshold: float | None = None


class ScenarioClassResult(BaseModel):
    scenario_class: str
    verdict: str  # PASS | FAIL | NOT_RUN | not_applicable


# =================================================================================================
# Inbound — gate result (an operation battery's raw outcome → SimForge persists + echoes)
# =================================================================================================


class AgentRunOutcome(BaseModel):
    agent_id: str
    module_id: str
    forge_id: str
    functions_certified: int
    functions_in_module: int  # DENOMINATOR
    passed: bool = True  # did the battery pass → certified vs failed (never a low score)
    max_certified_trust_tier: str | None = None  # auto_execute | propose | suggest
    operation_rubric_results: list[OperationRubricResultItem] = Field(default_factory=list)
    per_scenario_class_results: list[ScenarioClassResult] = Field(default_factory=list)
    failure_modes_observed: list[str] = Field(default_factory=list)
    version_sensitivity: dict[str, list[str]] = Field(default_factory=dict)
    expires_at: datetime | None = None


class DepartmentRunOutcome(BaseModel):
    department_id: str
    forge_id: str
    forge_context: str | None = None
    venture_context: str | None = None
    passed: bool = True
    escalation_path_verified: bool = False
    compliance_coupling_verified: bool = False


class GateResultRequest(BaseModel):
    instruction_set_ref: InstructionSetRef  # carries the Office-declared content_hash
    run_content_hash: str  # the hash the run ACTUALLY executed against
    run_ref: str | None = None
    operation_rubric_version: str | None = None  # defaults to the current engine version
    agent_outcomes: list[AgentRunOutcome] = Field(default_factory=list)
    department_outcomes: list[DepartmentRunOutcome] = Field(default_factory=list)


# =================================================================================================
# Outbound — gate result callback (SimForge → Office), Rev 2 shape
# =================================================================================================


class AgentOperationCertResult(BaseModel):
    agent_id: str
    module_id: str
    forge_id: str
    # certified | failed | not_run — plus `revoked` on a content-hash VOID (superset, documented).
    state: str
    max_certified_trust_tier: str | None = None
    operation_rubric_results: list[OperationRubricResultItem]  # NAMED LIST
    rubric_dimension_spread: float  # required — collapse check
    per_scenario_class_results: list[ScenarioClassResult] = Field(default_factory=list)
    functions_certified: int
    functions_in_module: int  # DENOMINATOR — always carried
    failure_modes_observed: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class DepartmentContextCertResult(BaseModel):
    department_id: str
    forge_id: str
    state: str  # certified | failed | not_run | revoked
    escalation_path_verified: bool
    compliance_coupling_verified: bool


class ForgeOperationResults(BaseModel):
    instruction_version_certified_under: str
    forge_api_version_certified_under: str
    instruction_content_hash: str  # ECHOED — mismatch VOIDS
    operation_rubric_version: str  # SEPARATE from the domain rubric_version
    agent_operation_certs: list[AgentOperationCertResult] = Field(default_factory=list)
    department_context_certs: list[DepartmentContextCertResult] = Field(default_factory=list)
    capability_matrix_delta: list[dict] = Field(default_factory=list)
