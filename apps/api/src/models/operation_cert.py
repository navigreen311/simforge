"""OperationCertification ORM model (Forge Operation Certification, Batch 2).

A certification unit at agent × forge × module granularity, SEPARATE from the 8-dimension DOMAIN
rubric and its certs (which are untouched). One table carries two unit types:

  Unit A (agent_operation):    agent_id × forge_id × module_id — can this agent drive the module?
  Unit B (department_context): department_id × forge_id × context — is the context cleared?

Hard invariants baked into the shape:
  - operation_rubric_version is REQUIRED and SEPARATE from the domain rubric_version. A change to
    either triggers re-cert for its OWN unit only; neither is optional.
  - The 7-state machine (see src/services/operation/state_machine.py) is stored as a distinct
    `state` string — never_certified / failed / stale_* are DISTINCT states, never a low score.
  - The DENOMINATOR travels on every Unit A result: functions_certified of functions_in_module.
  - operation_rubric_results is a NAMED-LIST JSON (not hardcoded dimension columns) so the rubric
    can finalize/extend without a schema change (Rev 2).
  - not_applicable is a first-class per-dimension verdict inside operation_rubric_results — never 0.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now


class OperationCertification(Base):
    __tablename__ = "OperationCertification"

    #: ADR-0070 - the collapse NUMBER and the RULE that produced it travel together or not at all.
    #: Stated as a constraint rather than as NOT NULL because a row may legitimately carry no
    #: number: a Unit B row has no rubric dimensions to compare. What may never happen is a number
    #: whose meaning is unknown - 0.0 is a collapsed variance under v1 and a clean sweep under v2,
    #: so an unlabelled number is not a weaker record, it is an unreadable one.
    __table_args__ = (
        CheckConstraint(
            '"rubricDimensionSpread" IS NULL OR "rubricSpreadMeasure" IS NOT NULL',
            name="operation_cert_spread_has_a_measure",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)

    # --- Common ---
    unitType: Mapped[str] = mapped_column(String, index=True)  # agent_operation|department_context
    state: Mapped[str] = mapped_column(String, index=True)  # 7-state machine (distinct states)
    forgeId: Mapped[str] = mapped_column(String, index=True)

    # Version matrix the cert was earned under (all bind targets).
    instructionVersion: Mapped[str] = mapped_column(String)  # semver
    forgeApiVersion: Mapped[str] = mapped_column(String)  # semver
    instructionContentHash: Mapped[str] = mapped_column(String)  # mismatch at run → VOID (Batch 4)
    # SEPARATE from and independent of the domain rubric_version — required, not optional.
    operationRubricVersion: Mapped[str] = mapped_column(String)  # semver
    #: WHICH ANSWER KEYS THE EXAM WAS GRADED AGAINST (ADR-0092 ruling 4).
    #:
    #: `instructionContentHash` says which INSTRUCTIONS the run executed against. It does not say
    #: which answer keys graded it, and until this column those were bound only by inference:
    #: `submitted_keys_for` selects by (forge, module, instruction hash), so an edited or added
    #: key changed the exam while the instruction hash stayed put and every row went on looking
    #: the same.
    #:
    #: Nullable, and the null means something: no submitted key was put, so this exam was graded
    #: against no answer key. A digest of the empty set would claim otherwise.
    scenarioSetHash: Mapped[str | None] = mapped_column(String, nullable=True)
    #: provider/model that ANSWERED the battery, e.g. `ollama/llama3.1:8b`.
    #:
    #: Everything above describes the EXAM — which instructions, which Forge version,
    #: which rubric. This is the CANDIDATE, and without it a row says *the agent passed*
    #: and cannot say *the agent, on this model, passed*: swap the model and the
    #: certification still reads as current.
    #:
    #: Nullable, and that is not the same as optional. A timed-out run got no answer, and
    #: a `department_context` unit is cleared by department state rather than by a model
    #: sitting an exam — both legitimately have nothing to name. The requirement is
    #: enforced where the verdict class is known, in the gate-result path, not by a
    #: NOT NULL that would be wrong for two real row shapes.
    agentModel: Mapped[str | None] = mapped_column(String, nullable=True)
    #: The candidate in full (ADR-0060) - model name, the model FILE with its size and
    #: quantization, the generation settings, and the fingerprint over all of it.
    #:
    #: Recorded on EVERY result, not only a certified one: a failed run's candidate is what makes
    #: the failure reproducible, and a provisional hold's is often the reason it was held. The
    #: version matrix above describes the EXAM and `agentModel` names the candidate; this is the
    #: only column that can say the candidate CHANGED.
    agentModelIdentity: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    #: Every attempt at the exam this certification records (ADR-0062). A pass means passed every
    #: attempt; this is the evidence for that sentence rather than a summary of it.
    #:
    #: NOT on `OperationRun` and not on the gate-result body, deliberately. The Office is entitled
    #: to WHETHER an agent passed and by how much against what threshold; how many times it sat
    #: the exam and what each attempt scored is SimForge's record of its own examination, and it
    #: is read back through `battery_result_for` - the second read, which is SimForge's own.
    examAttempts: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # --- Unit A: agent operation (nullable for Unit B rows) ---
    agentId: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    moduleId: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    functionsCertified: Mapped[int | None] = mapped_column(Integer, nullable=True)
    functionsInModule: Mapped[int | None] = mapped_column(Integer, nullable=True)  # DENOMINATOR
    maxCertifiedTrustTier: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # auto_execute | propose | suggest
    perScenarioClass: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {class: verdict}
    # NAMED LIST: [{dimension, verdict, score?, threshold?}] — not fixed columns.
    operationRubricResults: Mapped[list | None] = mapped_column(JSON, nullable=True)
    #: The run-level score this row was decided on, and WHAT IT MEASURES (ADR-0093).
    #:
    #: Stored here rather than only on the run, because a certification outlives the run it came
    #: from and is read on its own. `scoreMeasure` is a CHECK away from being optional: a number
    #: whose rule is unknown reads as 1.0-out-of-1.0 whatever it counted, which is how four rows
    #: came to look like clean passes beside three failing dimensions.
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    scoreMeasure: Mapped[str | None] = mapped_column(String, nullable=True)
    rubricDimensionSpread: Mapped[float | None] = mapped_column(Float, nullable=True)  # collapse
    #: WHICH RULE produced `rubricDimensionSpread` (ADR-0070). The measure is versioned, not
    #: migrated: rows written before v2 keep the population variance they were computed with and
    #: are labelled `population_variance_v1`, which is what they always were. NO default: the
    #: backfill was a one-time statement of fact about rows that already existed, not a standing
    #: answer for rows not yet written. Null only where there is no number to label - see the
    #: CHECK constraint above.
    rubricSpreadMeasure: Mapped[str | None] = mapped_column(String, nullable=True)
    #: WHY full certification was withheld (ADR-0072). A list of named reasons from
    #: `WITHHOLD_REASONS`, written only on a `provisional` row: a FAILED run was not withheld, and
    #: a CERTIFIED one has nothing to say here.
    #:
    #: Recorded rather than recomputed. Every reader used to re-derive the hold from the raw
    #: numbers - the web card rebuilt `collapsed` from the spread and the dimension count - which
    #: works until a rule changes and then explains old holds under a rule that never applied to
    #: them. The same lesson as `rubricSpreadMeasure`, one column along.
    withheldBecause: Mapped[list | None] = mapped_column(JSON, nullable=True)
    failureModesObserved: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Which version components (major/minor/patch) this cert is sensitive to, per module (Rev 2 Q4).
    versionSensitivity: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    expiresAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Unit B: department context (nullable for Unit A rows) ---
    departmentId: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    forgeContext: Mapped[str | None] = mapped_column(String, nullable=True)
    ventureContext: Mapped[str | None] = mapped_column(String, nullable=True)
    escalationPathVerified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    complianceCouplingVerified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # --- Common lifecycle ---
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    reviewedBy: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
