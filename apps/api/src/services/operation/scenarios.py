"""Operation scenario classes + curriculum submission validation (Batch 3).

The operation Scenario Bank tests whether an agent can DRIVE a Forge module. Nine scenario classes
exercise the five operation-rubric dimensions (Rev 2 Q1a). A curriculum submission is rejected if it
does not carry the scenarios required to back the verdicts it will report — a dimension with no
exercising scenario is a fake score (guarded at rubric build time in rubric.py; a *submission* that
omits the mandatory classes is guarded here).

CONTENT / SCORING BOUNDARY: this module is rubric-AGNOSTIC infrastructure. The concrete per-module
scenario CONTENT and the per-dimension pass/fail THRESHOLDS live behind the clearly-commented
"CONTENT LAYER" seam (SimForge authors that separately); nothing here hardcodes a threshold.

HELD-OUT SET / GATE 9.5 DEPENDENCY (flag — read this):
    The Office submits the curriculum + the instruction set; SimForge authors the HELD-OUT operation
    scenarios (notably `never_do_violation` and `silent_failure`) and does NOT expose them to The
    Office — otherwise an agent could be coached to the exact refusal/detection cases and the cert
    would measure memorization, not competence. This engine can validate a submission and can read
    the instruction set to author held-out scenarios, but it cannot, by itself, GUARANTEE that the
    party reading the instruction set to author the held-out set is isolated from the party that
    could leak it to The Office. That separation is an operational/process control — the SAME
    dependency Gate 9.5 rests on. `GATE_9_5_FLAG` is surfaced on every validation result so the
    caller (and the UI) never treats a "held-out authored" claim as self-proving.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from src.services.operation.rubric import OPERATION_DIMENSIONS, OperationDimension


class ScenarioClass(StrEnum):
    """The nine operation scenario classes. `recovery_after_failure` is the Rev 2 addition — it is
    DISTINCT from `silent_failure`/`partial_failure`: recognizing a failure and choosing the correct
    response to it are different competencies (rubric dims failure_recognition vs recovery)."""

    HAPPY_PATH = "happy_path"
    MALFORMED_INPUT = "malformed_input"
    PARTIAL_FAILURE = "partial_failure"
    SILENT_FAILURE = "silent_failure"
    RATE_LIMITED = "rate_limited"
    PERMISSION_DENIED = "permission_denied"
    NEVER_DO_VIOLATION = "never_do_violation"
    ESCALATION_REQUIRED = "escalation_required"
    RECOVERY_AFTER_FAILURE = "recovery_after_failure"


ALL_SCENARIO_CLASSES: tuple[str, ...] = tuple(c.value for c in ScenarioClass)

# SimForge authors these classes as the HELD-OUT set (not exposed to The Office). See GATE_9_5 note.
HELD_OUT_CLASSES: frozenset[str] = frozenset(
    {ScenarioClass.NEVER_DO_VIOLATION, ScenarioClass.SILENT_FAILURE}
)

# Every scenario must reference the instruction section it tests + declare its expectations.
REQUIRED_SCENARIO_FIELDS: tuple[str, ...] = (
    "instruction_section",
    "expected_behavior",
    "expected_escalation",
)

GATE_9_5_FLAG: str = (
    "held_out_authoring_is_a_process_control: SimForge authors the held-out "
    "never_do_violation/silent_failure scenarios and must keep them unseen by The Office; the "
    "engine cannot self-prove that isolation (same dependency as Gate 9.5)."
)

# --- CONTENT LAYER seam (documented) -------------------------------------------------------------
# Words in a never_do_violation scenario's expected_behavior that evidence the agent DECLINES the
# prohibited action. A light heuristic ONLY — the authoritative "did it decline" judgement is the
# held-out scenario's scoring (CONTENT LAYER), not this string check. Kept deliberately minimal.
_DECLINE_MARKERS: tuple[str, ...] = (
    "decline",
    "refus",
    "reject",
    "deny",
    "do not",
    "does not",
    "block",
)
# -------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CurriculumValidation:
    """Result of validating a curriculum submission.

    `violations` non-empty ⇒ REJECT the submission. `module_levels` labels each module
    "certified" (all nine classes present) or "demonstrated" (happy-path-only or otherwise
    incomplete) — a label, NOT a rejection: a demonstrated module is honestly not certified.
    """

    violations: list[str]
    module_levels: dict[str, str]  # module_id -> "certified" | "demonstrated"
    gate_9_5_flag: str = GATE_9_5_FLAG

    @property
    def rejected(self) -> bool:
        return bool(self.violations)


def classify_certification_level(classes_present: Iterable[str]) -> str:
    """A module is certifiable only if EVERY scenario class is present. A module tested only on
    happy_path (or missing any class) is "demonstrated", never "certified" (Batch 3)."""
    present = set(classes_present)
    return "certified" if set(ALL_SCENARIO_CLASSES) <= present else "demonstrated"


def _proves_decline(scenario: Mapping) -> bool:
    if scenario.get("proves_decline") is True:
        return True
    behavior = str(scenario.get("expected_behavior", "")).lower()
    return any(m in behavior for m in _DECLINE_MARKERS)


def validate_curriculum_submission(
    scenarios: Sequence[Mapping],
    *,
    module_never_do: Mapping[str, Sequence[str]] | None = None,
    requested_modules: Iterable[str] | None = None,
    rubric_dimensions: tuple[OperationDimension, ...] = OPERATION_DIMENSIONS,
) -> CurriculumValidation:
    """Validate a submitted operation curriculum against the Batch 3 rules.

    Rejections (each appended to `violations`):
      - a scenario missing instruction_section / expected_behavior / expected_escalation,
      - a scenario with an unknown scenario_class or no module_id,
      - a module with NO escalation_required scenario (escalation_required is mandatory),
      - a module whose rubric includes the `recovery` dimension but has NO recovery_after_failure
        scenario (recovering after a failure is distinct from recognizing one — its own class),
      - a never-do list entry with no never_do_violation scenario, or one that does not prove the
        agent DECLINES.

    Not a rejection (a LABEL): a module missing some non-mandatory class → "demonstrated".
    """
    module_never_do = module_never_do or {}
    violations: list[str] = []
    by_module: dict[str, list[Mapping]] = defaultdict(list)

    for idx, s in enumerate(scenarios):
        sc = s.get("scenario_class")
        if sc not in set(ALL_SCENARIO_CLASSES):
            violations.append(f"scenario[{idx}]: unknown scenario_class {sc!r}")
            continue
        mod = s.get("module_id")
        if not mod:
            violations.append(f"scenario[{idx}] ({sc}): missing module_id")
            continue
        missing = [f for f in REQUIRED_SCENARIO_FIELDS if not s.get(f)]
        if missing:
            violations.append(
                f"scenario[{idx}] (module {mod}, {sc}): missing {', '.join(missing)}"
            )
        by_module[str(mod)].append(s)

    rubric_has_recovery = any(d.key == "recovery" for d in rubric_dimensions)
    modules = set(requested_modules) if requested_modules is not None else set(by_module)
    module_levels: dict[str, str] = {}

    for mod in sorted(modules):
        classes_present = {str(s["scenario_class"]) for s in by_module.get(mod, [])}

        if ScenarioClass.ESCALATION_REQUIRED not in classes_present:
            violations.append(f"module {mod}: no escalation_required scenario (mandatory)")

        if rubric_has_recovery and ScenarioClass.RECOVERY_AFTER_FAILURE not in classes_present:
            violations.append(
                f"module {mod}: rubric includes the recovery dimension but has no "
                f"recovery_after_failure scenario"
            )

        nd_entries = list(module_never_do.get(mod, []))
        if nd_entries:
            nd_scenarios = [
                s
                for s in by_module.get(mod, [])
                if str(s.get("scenario_class")) == ScenarioClass.NEVER_DO_VIOLATION
            ]
            for entry in nd_entries:
                matches = [s for s in nd_scenarios if s.get("never_do_entry") == entry]
                if not matches:
                    violations.append(
                        f"module {mod}: never-do entry {entry!r} has no never_do_violation scenario"
                    )
                elif not any(_proves_decline(s) for s in matches):
                    violations.append(
                        f"module {mod}: never-do entry {entry!r} scenario does not prove the agent "
                        f"DECLINES"
                    )

        module_levels[mod] = classify_certification_level(classes_present)

    return CurriculumValidation(violations=violations, module_levels=module_levels)


__all__ = [
    "ScenarioClass",
    "ALL_SCENARIO_CLASSES",
    "HELD_OUT_CLASSES",
    "REQUIRED_SCENARIO_FIELDS",
    "GATE_9_5_FLAG",
    "CurriculumValidation",
    "classify_certification_level",
    "validate_curriculum_submission",
]
