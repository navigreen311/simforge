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
  - `module_not_applicable` declares a class a module cannot have, per class per module, and the
    REASON IS REQUIRED — an entry with an empty one is refused at the schema (ADR-0049). A declared
    n/a is not a pass: it carries `not_applicable` and no score, never a zero.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

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
    # Declared not_applicable, per class per module: module_id -> scenario_class -> WHY (ADR-0049).
    # A class a module genuinely cannot have is STATED here rather than left absent, so an absence
    # nobody considered stays distinguishable from one somebody ruled on. The reason is prose and it
    # is REQUIRED — an entry with an empty one is refused below, because an empty string cannot tell
    # a considered absence from an accidental one (NoFramework's four-of-nine accidental empties are
    # why this is mandatory rather than encouraged). A declared n/a is NOT a pass: it carries
    # not_applicable and NO score, never a zero.
    module_not_applicable: dict[str, dict[str, str]] = Field(default_factory=dict)

    @field_validator("module_not_applicable")
    @classmethod
    def _reason_is_required(
        cls, value: dict[str, dict[str, str]]
    ) -> dict[str, dict[str, str]]:
        """Refuse a declaration that skips the sentence — the whole point of the primitive.

        Enforced HERE, in the schema, so it is refused before the curriculum validator runs, the
        way every other required-field rule on this payload is (contract §6). Whether a *missing*
        class is a rejection, and which classes are mandatory, is the validator's ruling and is
        deliberately not decided here — this only refuses a declaration that says nothing.
        """
        for module_id, per_module in value.items():
            for scenario_class, why in per_module.items():
                if not why.strip():
                    raise ValueError(
                        f"module {module_id}: {scenario_class!r} declared not_applicable with no "
                        "reason. Say why this class cannot apply to this module; an absence "
                        "without a sentence cannot be told from one nobody considered."
                    )
        return value


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
    #: provider/model that ANSWERED the battery, e.g. `ollama/llama3.1:8b`.
    #:
    #: Optional on the wire and NOT optional in a certification: `gate_result` refuses to
    #: persist a certified or provisional `agent_operation` row without one. Optional here
    #: so a caller that omits it gets a REFUSAL naming the missing fact, rather than a 422
    #: naming the shape — the two need different responses, and only the first says what
    #: is actually wrong.
    agent_model: str | None = None
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


# =================================================================================================
# Run window — a battery in flight, and the verdict a run that never finished resolves to
# =================================================================================================


class OperationRunStartRequest(BaseModel):
    """Hand-over: a battery is starting. Idempotent on `run_ref`.

    Without this call SimForge holds no record of a run between the curriculum and the
    gate result, so a battery that hangs produces nothing at all — no row, no verdict, no
    error — and TIMEOUT is unreachable. `unit` is declared HERE rather than inferred at
    the end because The Office reads one verdict per `run_ref`, and a run whose unit is
    only known once it finishes cannot be asked about while it is hanging.
    """

    run_ref: str
    unit: str  # "A" (agent x forge x module) | "B" (department x forge)
    forge_id: str
    instruction_content_hash: str  # the basis this run executes against
    rubric_kind: str = "operation"  # operation | domain — never a merged score
    rubric_version: str | None = None  # defaults to the current operation rubric version
    module_id: str | None = None
    agent_id: str | None = None
    department_id: str | None = None
    scenario_count: int = 0
    coverage_denominator: int = 0
    #: The window this run is judged against, fixed at start. A run is never re-judged
    #: against a default that changed while it was running.
    window_minutes: int | None = None


class OperationRunStarted(BaseModel):
    run_ref: str
    unit: str
    started_at: datetime
    window_minutes: int
    #: True when this ref was already open — the clock was NOT restarted. A retried
    #: hand-over must not extend the window of a run that is already hanging.
    already_open: bool


class TimedOutRun(BaseModel):
    run_ref: str
    unit: str
    forge_id: str
    module_id: str | None = None
    agent_id: str | None = None
    department_id: str | None = None
    verdict: str  # always TIMEOUT
    minutes_open: float
    window_minutes: int
    #: Deliberately absent: score. A timed-out run carries none — zero would be a claim
    #: about the agent rather than about the run.


class TimeoutSweepResult(BaseModel):
    swept_at: datetime
    timed_out: list[TimedOutRun] = Field(default_factory=list)


# =================================================================================================
# Outbound — how much held-out material exists, never what it says (ADR-0050)
# =================================================================================================


class HeldOutInventoryResponse(BaseModel):
    """Counts and a digest for one module's held-out set. **There is no content field, and that is
    the design rather than an omission.**

    ADR-0050 ruled that no credential fetches the held-out set, because an endpoint returning the
    corpus makes isolation a function of who holds a token. An operator still has a real question —
    was this module's refusal material ever authored, and against how many obligations — so the
    shape is inspectable and the content is not: *"eleven scenarios exist for this module" is
    inspectable; "here they are" is the exam.*

    `digest` is one-way. It makes "the same set as last week" checkable without anybody reading a
    scenario, which is the audit property that would otherwise have justified returning them.

    **Deliberately absent, and it was permitted:** per-scenario obligation ids. The ruling allows
    ids; they are left out because an id says which of the submitter's OWN never-do entries drew a
    `silent_failure` probe, and that answers no operator question while being a fact about the exam.
    """

    forge_id: str
    module_id: str
    #: How many never-do entries this module declared. 0 ⇒ nothing to author, genuinely not a hole.
    obligations_declared: int
    #: How many probes were authored from them. A claim prohibition yields two, an act one.
    scenarios_authored: int
    #: scenario_class -> count, e.g. {"never_do_violation": 7, "silent_failure": 5}
    by_class: dict[str, int] = Field(default_factory=dict)
    digest: str
    #: Carried here for the same reason it is carried on a validation result: a reader must never
    #: treat a "held-out authored" count as proof the isolation behind it holds.
    gate_9_5_flag: str
