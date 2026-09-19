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

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# =================================================================================================
# Inbound — curriculum submission (Office → SimForge)
# =================================================================================================


#: The four acts `RESPONSE_PROTOCOL` offers, as an expected answer may name them. `REFUSE` is
#: written bare here: the protocol requires the agent to append the prohibition NUMBER, and which
#: number is a fact about the module's never-do list rather than about the key.
EXPECTED_ACTS: frozenset[str] = frozenset({"PROCEED", "REFUSE", "DECLINE", "ESCALATE"})


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


class ExpectedAnswer(BaseModel):
    """The shape the submitter expects, beside the prose (ADR-0069 ruling 2, ADR-0077, ADR-0082).

    **Transcription, not judgment.** The grader compares the agent's parsed ACT and RECORD to these
    fields by exact equality. No model reads either side's prose, which is what `_DECLINE_MARKERS`
    was deleted for (ADR-0048) and what the held-out battery was built around (ADR-0051).

    `record_subject` is NAMED TO THE AGENT (ADR-0077): the exam renders it into the probe, so the
    string the agent is shown and the string the grader compares are this one field and cannot
    drift. The same goes for `record_claim_options` when the claim is an enum.
    """

    model_config = ConfigDict(extra="forbid")

    #: PROCEED | REFUSE <n> | DECLINE | ESCALATE - the four the protocol offers.
    act: str
    #: `NONE` when the expected answer records nothing. Mutually exclusive with the pair below.
    record: str | None = None
    record_subject: str | None = None
    record_claim: str | None = None
    #: The permitted claims, named to the agent. **One list per (module, subject), always** - a list
    #: that varied per probe would say which scenario is being put, the same leak the naming
    #: sentence avoids.
    record_claim_options: list[str] | None = None
    #: A qualification the answer must carry, graded as PRESENT rather than word for word
    #: (ADR-0082 rulings 7-10). Records an expectation that no grader reaches YET:
    #: `ObservedBehaviour.disclosed` is written at one site and read at none.
    expected_caveat: str | None = None

    @model_validator(mode="after")
    def _one_record_form(self) -> ExpectedAnswer:
        if self.act not in EXPECTED_ACTS:
            raise ValueError(
                f"expected_answer.act {self.act!r} is not one of {sorted(EXPECTED_ACTS)}. "
                "A key naming an act the protocol does not offer expects an answer no agent "
                "can give."
            )
        records_nothing = (self.record or "").upper() == "NONE"
        names_a_fact = self.record_subject is not None or self.record_claim is not None
        if records_nothing and names_a_fact:
            raise ValueError(
                "expected_answer declares `record: NONE` and a subject or claim. The protocol "
                "allows one RECORD line and it is one or the other."
            )
        if not records_nothing and not names_a_fact:
            raise ValueError(
                "expected_answer declares neither `record: NONE` nor a subject and claim. An "
                "expectation that says nothing about the RECORD line cannot be transcribed."
            )
        if names_a_fact and (self.record_subject is None or self.record_claim is None):
            raise ValueError(
                "expected_answer names a record subject without a claim, or a claim without a "
                "subject. Both halves or neither."
            )
        if self.record_claim_options is not None:
            if records_nothing:
                raise ValueError(
                    "expected_answer declares `record: NONE` and a list of claim options. There "
                    "is nothing for the options to be options FOR."
                )
            if self.record_claim not in self.record_claim_options:
                raise ValueError(
                    f"expected_answer.record_claim {self.record_claim!r} is not among its own "
                    f"options {self.record_claim_options!r}. A key whose right answer is not on "
                    "the list the agent is shown cannot be satisfied."
                )
        return self


class OperationScenarioSubmission(BaseModel):
    #: ADR-0083: an undeclared field is REFUSED, not dropped. Pydantic's default is to ignore
    #: extras, so before this a submitter could send `expected_answer` and have it silently
    #: discarded - both sides believing an answer key had been delivered when none had.
    model_config = ConfigDict(extra="forbid")

    scenario_class: str  # one of ScenarioClass
    module_id: str
    instruction_section: str  # which section of the instruction set it tests
    #: THE PROBE - what the agent is asked (ADR-0087). Without it SimForge holds a key and has
    #: nothing to put: the grader is complete and its input does not exist.
    #:
    #: **It must never be `expected_behavior`.** That field is what a good answer looks like, and
    #: rendering it into a probe would hand the agent the answer. The Office holds this in
    #: `summary` and says so: "there is no `situation` field on either side of the [wire]" - this
    #: is SimForge declaring the side it owns, which `extra="forbid"` makes the required first
    #: step.
    #:
    #: Optional, because The Office does not send it yet and a required field would refuse every
    #: curriculum it currently submits. See `probe_for` for what an absence costs.
    situation: str | None = None
    expected_behavior: str
    expected_escalation: str
    never_do_entry: str | None = None  # for never_do_violation scenarios
    #: The transcribable half of the key. Optional while the 44 split keys are still drafts; a
    #: scenario without one can be stored and cannot be graded by transcription.
    expected_answer: ExpectedAnswer | None = None


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
    #: The tier this exam can justify at MOST — a ceiling, not a measurement. The gate-result path
    #: caps it by state (`trust_tier.tier_for_state`), so a caller declaring `auto_execute` on a
    #: failed outcome does not thereby record one.
    max_certified_trust_tier: str | None = None  # auto_execute | propose | suggest
    #: The run-level score and the bar it was judged against. BOTH optional and both meaningless
    #: alone: a score without a threshold is a number nobody can place, and The Office is entitled
    #: to read the bar (`simforge_response_manifest.json`). Optional on the wire and NOT optional
    #: in a certification — `gate_result` refuses to persist a `certified` agent_operation row
    #: without them, for the reason it already refuses one that names no `agent_model`: a pass
    #: whose basis is absent is one nobody can check.
    #:
    #: `None` is never 0.0 here. A battery that graded no probe has no score, and a zero would be
    #: a claim about the agent rather than about the run.
    score: float | None = None
    threshold: float | None = None
    #: provider/model that ANSWERED the battery, e.g. `ollama/llama3.1:8b`.
    #:
    #: Optional on the wire and NOT optional in a certification: `gate_result` refuses to
    #: persist a certified or provisional `agent_operation` row without one. Optional here
    #: so a caller that omits it gets a REFUSAL naming the missing fact, rather than a 422
    #: naming the shape — the two need different responses, and only the first says what
    #: is actually wrong.
    agent_model: str | None = None
    #: WHAT answered, not just what it was called (ADR-0060). `agent_model` above is a label; the
    #: same tag re-pulled at a different quantization, or served at a different temperature,
    #: produces that identical string and a different candidate. This is the candidate: model
    #: name, the model FILE with its size and quantization, and the generation settings the exam
    #: was actually put under.
    #:
    #: Optional on the wire and NOT optional in a certification, for the reason every other fact
    #: here is: the refusal has to name which fact is missing, and a 422 about the shape cannot.
    #: `gate_result` refuses to certify an outcome whose identity is absent or incomplete, and
    #: holds one carrying no model FILE at `provisional` — a cloud provider is for practice runs,
    #: and a practice run is not a certification.
    model_identity: dict | None = None
    #: Every attempt at this exam, in the order they were sat (ADR-0062). A pass means passed
    #: EVERY attempt, so this is what lets a reader tell a clean three-of-three from a lucky
    #: two-of-three - and on a FAIL, which attempt failed and how.
    #:
    #: Small and deliberately not transcripts: verdict, score, probes put, unreadable answers and
    #: failure modes per attempt. None of it is scenario content.
    attempts: list[dict] = Field(default_factory=list)
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
    model_identity: dict | None = None
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

    #: ADR-0083: an undeclared field is REFUSED, not dropped.
    model_config = ConfigDict(extra="forbid")

    run_ref: str
    unit: str  # "A" (agent x forge x module) | "B" (department x forge)
    forge_id: str
    instruction_content_hash: str  # the basis this run executes against
    rubric_kind: str = "operation"  # operation | domain — never a merged score
    rubric_version: str | None = None  # defaults to the current operation rubric version
    module_id: str | None = None
    agent_id: str | None = None
    department_id: str | None = None
    #: WHO IS SITTING THE EXAM, in the Village's own vocabulary (`victor_serath`), not The
    #: Office's uuid.
    #:
    #: `agent_id` above is consumed as a VILLAGE ref by `check_agent_identity`, and The Office
    #: sends its `office_agent_id` there - so every run it opened in September refused on identity
    #: and six rows were corrected by hand from `office_agent_identity.village_agent_ref`. This is
    #: that column crossing the boundary instead.
    #:
    #: Optional, because The Office does not send it yet. When it is absent the battery falls back
    #: to `agent_id` and fails exactly as it does today - loudly, by name, never quietly.
    village_agent_ref: str | None = None
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
