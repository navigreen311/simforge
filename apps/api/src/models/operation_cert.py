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

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now


class OperationCertification(Base):
    __tablename__ = "OperationCertification"

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
    rubricDimensionSpread: Mapped[float | None] = mapped_column(Float, nullable=True)  # collapse
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
