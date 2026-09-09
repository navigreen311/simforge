"""Operation scenario classes + curriculum submission validation (Batch 3).

The operation Scenario Bank tests whether an agent can DRIVE a Forge module. Nine scenario classes
exercise the five operation-rubric dimensions (Rev 2 Q1a). A curriculum submission is rejected if it
does not carry the scenarios required to back the verdicts it will report — a dimension with no
exercising scenario is a fake score (guarded at rubric build time in rubric.py; a *submission* that
omits the mandatory classes is guarded here).

DECLARED ABSENCE (ADR-0049, built by P-02 in `never_do.py`, enforced here):
    The validator used to assert that every module is the same shape, and they are not. A module
    that writes has partial state, a retry hazard and a failure worth escalating; a module that
    does not write has none of those. `capitalforge/portfolio_health` takes no identifier, writes
    nothing, and its RETRY VS ESCALATE section reads "Retry freely." in full — there is no failure
    to hand a human, so `escalation_required` has no honest content at any level of effort, and
    authoring one anyway would certify an agent for handling an escalation the module cannot
    produce.

    So a class a module genuinely cannot have may be DECLARED not_applicable, with a reason in
    prose, and the submission is accepted. **A class that is neither supplied nor declared is still
    refused.** That distinction is the whole of it: a declared absence is an answer and a bare
    absence is not, and nothing here lets silence pass as a considered judgement. Declarations
    arrive as `module_not_applicable` on the curriculum — module -> class -> reason (contract §10
    A1.1) — never as a scenario row.

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

    **The split is now ENFORCED on the submission side (ADR-0048).** A submitted scenario carrying
    a held-out class is refused. It used to be accepted, which meant the party being certified
    could supply its own refusal test — the isolation was a rule with no enforcement on the only
    side that could break it. Enforcing it does not make the isolation self-proving; the flag above
    still stands, because refusing what arrives says nothing about who authored what does not.

    **The authoring side now exists: `held_out.py`.** ADR-0048 moved the never-do refusal to
    scoring time and left nobody at the other end, so every module declaring a never-do list sat at
    `provisional` — a correct refusal of work the submitter was forbidden to do and SimForge had no
    pipeline to do either. `held_out.author_for_module` takes the declared never-do list and
    authors both held-out classes from it, because that one list carries both kinds of obligation:
    a prohibition on an ACT is a `never_do_violation` case and a prohibition on a CLAIM
    ("never report `score: null` as zero") is a `silent_failure` one. `classify_certification_level`
    takes what it produced as `held_out_authored`; nothing at SUBMISSION time does, and nothing
    should — at submission those scenarios do not exist yet, which is the whole of ADR-0048.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from src.services.operation.never_do import (
    CLASS_ABSENT,
    NotApplicableDeclaration,
    NotApplicableDeclarationError,
    classify_scenario_class,
    declarations_from_map,
)
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

# --- Certification levels (ADR-0049 / P-03's ruling) ---------------------------------------------
# Three, not two. `certified` still means EXACTLY what it meant — every one of the nine classes was
# SUPPLIED — and it is never widened by a declaration. The third value exists because the two
# readings ADR-0049 names were the same word:
#
#     demonstrated because the curriculum is incomplete and somebody should finish it
#     demonstrated because a required class describes behaviour this module does not have
#
# The first needs someone to finish the work; the second needs nobody. A declared, reasoned
# not_applicable is what separates them, and this is where that separation becomes readable.
LEVEL_CERTIFIED = "certified"  # all nine SUPPLIED — unchanged meaning, never widened
# the rest declared not_applicable, each with a reason:
LEVEL_CERTIFIED_WITH_DECLARED_ABSENCE = "certified_with_declared_absence"
LEVEL_DEMONSTRATED = "demonstrated"  # a class is neither supplied nor declared — nobody said

CERTIFICATION_LEVELS: tuple[str, ...] = (
    LEVEL_CERTIFIED,
    LEVEL_CERTIFIED_WITH_DECLARED_ABSENCE,
    LEVEL_DEMONSTRATED,
)

GATE_9_5_FLAG: str = (
    "held_out_authoring_is_a_process_control: SimForge authors the held-out "
    "never_do_violation/silent_failure scenarios and must keep them unseen by The Office; the "
    "engine cannot self-prove that isolation (same dependency as Gate 9.5)."
)

# --- CONTENT LAYER seam (documented) -------------------------------------------------------------
# There was a `_DECLINE_MARKERS` word-list here, checking that a submitted never_do_violation
# scenario's expected_behavior evidenced the agent DECLINING. **Removed by ADR-0048's ruling, and
# this note is left in its place so the removal is found rather than inferred.**
#
# It was a light heuristic over a submitted scenario, and its own comment said the authoritative
# "did it decline" judgement was the held-out scenario's SCORING, never the string check. After the
# ruling a submitter may not send a never_do_violation scenario at all, so the heuristic could only
# ever have run on a payload that is now refused one check earlier. Deleting an unreachable
# approximation of a judgement that lives elsewhere is not the same as dropping the judgement: the
# `never_do_adherence` rubric dimension is where declining is actually decided, and
# `never_do.is_never_do_coverage_hole` is what refuses a declared obligation that was never
# exercised there.
# -------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CurriculumValidation:
    """Result of validating a curriculum submission.

    `violations` non-empty ⇒ REJECT the submission. `module_levels` labels each module with one of
    `CERTIFICATION_LEVELS` — a label, NOT a rejection.

    `never_do_obligations` is module → the declared never-do entries, recorded rather than checked:
    a submitter may not author the `never_do_violation` scenarios that would test them, so whether
    each was exercised is decided at scoring time (ADR-0048). Carrying them out of the validator is
    what keeps "declared and not yet tested" visible instead of silent.

    `module_declared_absences` is module → class → why, echoing every declaration that was accepted.
    It exists because **a label alone cannot surface a cap.** ADR-0049 requires that a declared
    absence be visible "in the coverage view, in the module's cert row, or wherever `demonstrated`
    is rendered", and deliberately does not design that. This is the smallest honest version: the
    reasons travel out of the validator attached to the module they are about, so a reader of the
    result has the sentence and not just the verdict.
    """

    violations: list[str]
    module_levels: dict[str, str]  # module_id -> one of CERTIFICATION_LEVELS
    module_declared_absences: dict[str, dict[str, str]] = field(default_factory=dict)
    never_do_obligations: dict[str, list[str]] = field(default_factory=dict)
    gate_9_5_flag: str = GATE_9_5_FLAG

    @property
    def rejected(self) -> bool:
        return bool(self.violations)


def classify_certification_level(
    classes_present: Iterable[str],
    *,
    declared_not_applicable: Iterable[str] = (),
    held_out_authored: Iterable[str] = (),
) -> str:
    """Which level one module reaches, given what it supplied and what it declared absent.

    **`certified` is unchanged and is never widened.** It still means every one of the nine classes
    was SUPPLIED. A declaration does not buy it, because a module that cannot exercise a class has
    not been shown to handle it and saying otherwise would be the pass-over-a-situation-that-cannot-
    occur that ADR-0049 refuses.

    What changes is the OTHER end. A class that is **declared not_applicable with a reason** is an
    ANSWER; a class that is simply absent is not. Before this, both produced `demonstrated`, and a
    reader could not tell "somebody should finish this" from "this class does not exist here".
    Now:

        all nine supplied                          -> certified
        the rest declared not_applicable, w/ reason -> certified_with_declared_absence
        anything neither supplied nor declared      -> demonstrated

    **HELD-OUT classes are struck from the declarations before they count.** A submitter cannot
    declare away `never_do_violation` or `silent_failure`: those are SimForge's to author, and a
    submitter that could declare them inapplicable would be excusing itself from the two classes
    that test refusal and concealment. It also keeps the contract's §1.1 ceiling exactly where it
    was — an Office submission can supply at most seven of nine and therefore still cannot reach
    either certified level on its own.

    **This ruling is deliberately the conservative half.** Whether a module carrying a declared
    absence *should* be certifiable is a governance question that ADR-0049 and contract §2.1 both
    leave open, and it is not settled here. What is settled is that the cap stops being silent —
    which is what makes the governance question askable with data instead of by memory.

    **`held_out_authored` is what SimForge itself supplied** (`held_out.authored_classes`), and it
    is a SEPARATE argument from `classes_present` rather than something a caller folds in, so that
    the two sources of supply can never be confused at a call site. It counts as SUPPLIED, because
    it IS supplied — the scenario exists, it was authored against a declared obligation, and it is
    graded like any other class. Without it the seven-of-nine ceiling in contract §1.1 was not a
    ceiling on The Office, it was a ceiling on every module in the system: the two classes nobody
    was permitted to submit were also the two nobody was authoring, so a never-do list bought a
    module a permanent `demonstrated`.

    **Only a HELD-OUT class may arrive this way, and passing anything else raises.** A caller that
    could hand a submittable class in as "authored by SimForge" would have found a route around the
    validator's rejection of that class — the refusal ADR-0048 added on the only side that could
    break it. Refusing here keeps this parameter a door for the two classes it was cut for.

    Defaults to `()`, so every existing caller behaves exactly as it did.
    """
    authored = set(held_out_authored)
    smuggled = authored - HELD_OUT_CLASSES
    if smuggled:
        raise ValueError(
            f"held_out_authored may only carry HELD-OUT classes; got {sorted(smuggled)}. A class a "
            f"submitter is allowed to send must be counted as SUBMITTED, through classes_present "
            f"and the validator that checks it — routing one through here would be a way past the "
            f"rejection ADR-0048 added."
        )
    present = set(classes_present) | authored
    if set(ALL_SCENARIO_CLASSES) <= present:
        return LEVEL_CERTIFIED
    declared = set(declared_not_applicable) - HELD_OUT_CLASSES
    if set(ALL_SCENARIO_CLASSES) <= (present | declared):
        return LEVEL_CERTIFIED_WITH_DECLARED_ABSENCE
    return LEVEL_DEMONSTRATED


def validate_curriculum_submission(
    scenarios: Sequence[Mapping],
    *,
    module_never_do: Mapping[str, Sequence[str]] | None = None,
    module_not_applicable: Mapping[str, Mapping[str, str]] | None = None,
    requested_modules: Iterable[str] | None = None,
    rubric_dimensions: tuple[OperationDimension, ...] = OPERATION_DIMENSIONS,
) -> CurriculumValidation:
    """Validate a submitted operation curriculum against the Batch 3 rules + ADR-0049.

    Rejections (each appended to `violations`):
      - a scenario missing instruction_section / expected_behavior / expected_escalation,
      - a scenario with an unknown scenario_class or no module_id,
      - a module with NO escalation_required scenario **and no declaration that it cannot have
        one** (escalation_required is mandatory),
      - a module whose rubric includes the `recovery` dimension but has NO recovery_after_failure
        scenario and no declaration (recovering after a failure is distinct from recognizing one —
        its own class),
      - a scenario whose class is HELD OUT (`never_do_violation`, `silent_failure`) — SimForge
        authors those and a submitter may not send one (ADR-0048),
      - a not_applicable declaration that is malformed: no reason, an unknown scenario_class, a
        module that was not submitted, or a class that this module also supplied.

    **No longer a rejection (ADR-0048, path B):** a declared never-do entry with no matching
    `never_do_violation` scenario. That check asked the submitter for a class the submitter is
    forbidden to author, so no correct submission could declare a never-do list at all. The
    obligation is now RECORDED (`never_do_obligations`) and its coverage is decided at scoring
    time, where SimForge's own held-out scenarios exist — see `never_do.is_never_do_coverage_hole`,
    which still blocks full certification for an obligation that was never exercised. **The refusal
    moved; it was not dropped.**

    **The whole of ADR-0049 in one sentence: a DECLARED absence is an answer and a bare absence is
    not.** A mandatory class that nobody supplied and nobody declared is still refused, exactly as
    before — a class nobody considered must not slip through as "presumably fine". What is new is
    that a module which genuinely cannot exercise a class may now say so, in prose, and be accepted.

    `module_not_applicable` is the wire map from `ForgeOperationCurriculum` (contract §10 A1.1):
    module -> class -> reason. It is NOT a scenario row, and this function never looks for one.

    Not a rejection (a LABEL): the certification level — see `classify_certification_level`.
    """
    module_never_do = module_never_do or {}
    violations: list[str] = []
    by_module: dict[str, list[Mapping]] = defaultdict(list)

    # Parse the declarations through P-02's single parse point, so the required-reason rule is the
    # SAME rule whether a declaration arrived over the wire or was built in process. A malformed map
    # is refused whole: `declarations` stays empty, every mandatory class is then genuinely absent,
    # and the submission collects those violations too. That cascade is honest — nothing was
    # declared — and the first violation names the real cause.
    declarations: dict[str, dict[str, NotApplicableDeclaration]] = {}
    if module_not_applicable:
        try:
            declarations = declarations_from_map(module_not_applicable)
        except NotApplicableDeclarationError as exc:
            violations.append(f"not_applicable declaration refused: {exc}")

    for idx, s in enumerate(scenarios):
        sc = s.get("scenario_class")
        if sc not in set(ALL_SCENARIO_CLASSES):
            violations.append(f"scenario[{idx}]: unknown scenario_class {sc!r}")
            continue
        if sc in HELD_OUT_CLASSES:
            # ADR-0048's second half. A submitter must not author the classes that test refusal and
            # concealment: accepting one lets the party being certified supply its own refusal test,
            # and the cert then measures what it was handed. Until now nothing refused it — the
            # held-out split was a rule with no enforcement on the only side that could break it.
            #
            # `continue`, so the refused scenario is not counted as supplied either. A scenario that
            # was rejected must not go on to raise the module's certification level.
            violations.append(
                f"scenario[{idx}] (module {s.get('module_id')}, {sc}): {sc} is a HELD-OUT class. "
                f"SimForge authors it and a submitter may not send one — an agent graded against "
                f"refusal cases its own authoring system wrote is measured on memorisation, not "
                f"competence. Declare the obligation (module_never_do) and leave the scenario to "
                f"SimForge."
            )
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
    module_declared_absences: dict[str, dict[str, str]] = {}
    never_do_obligations: dict[str, list[str]] = {}

    # A declaration about a module that was not submitted is a statement about nothing, and the
    # likeliest cause is a mistyped module id — in which case the module the author MEANT to
    # declare for still has an undeclared class and is about to be refused for it, while the author
    # believes they declared it. Naming it is the difference between one clear refusal and two
    # confusing ones.
    for declared_module in sorted(set(declarations) - modules):
        violations.append(
            f"not_applicable declaration for module {declared_module!r}, which is not in this "
            f"submission. A declaration about a module nobody submitted states nothing; check the "
            f"module id."
        )

    for mod in sorted(modules):
        classes_present = {str(s["scenario_class"]) for s in by_module.get(mod, [])}
        module_declarations = declarations.get(mod, {})

        for declared_class, decl in sorted(module_declarations.items()):
            # §1: an unknown class is a rejection BY DESIGN, so that a class nobody considered
            # cannot pass as one somebody did. P-02's parser deliberately leaves this check here.
            if declared_class not in set(ALL_SCENARIO_CLASSES):
                violations.append(
                    f"module {mod}: not_applicable declares unknown scenario_class "
                    f"{declared_class!r}"
                )
            # Both supplied and declared absent. Two contradictory statements about one slot, and
            # nothing downstream could say which one the cert should carry — the same reason
            # `index_declarations` refuses one class declared twice.
            elif declared_class in classes_present:
                violations.append(
                    f"module {mod}: {declared_class!r} is declared not_applicable and also "
                    f"supplied as a scenario. A class cannot both not apply and be exercised."
                )
            else:
                module_declared_absences.setdefault(mod, {})[declared_class] = decl.why

        # --- the mandatory classes -------------------------------------------------------------
        # Supplied / declared-with-a-reason / absent, told apart by P-02's primitive. Only the
        # third is a rejection: the absence has to be STATED, and silence is not a statement.
        escalation_state = classify_scenario_class(
            ScenarioClass.ESCALATION_REQUIRED,
            supplied_classes=classes_present,
            declarations=module_declarations,
        )
        if escalation_state == CLASS_ABSENT:
            violations.append(
                f"module {mod}: no escalation_required scenario (mandatory). If this module cannot "
                f"have one, declare it not_applicable with a reason — an absence nobody stated "
                f"cannot be told from one nobody considered."
            )

        if rubric_has_recovery:
            recovery_state = classify_scenario_class(
                ScenarioClass.RECOVERY_AFTER_FAILURE,
                supplied_classes=classes_present,
                declarations=module_declarations,
            )
            if recovery_state == CLASS_ABSENT:
                violations.append(
                    f"module {mod}: rubric includes the recovery dimension but has no "
                    f"recovery_after_failure scenario, and none was declared not_applicable"
                )

        # --- the declared never-do list (ADR-0048, resolved: path B) ---------------------------
        # This block used to REJECT a declared never-do entry that had no matching
        # never_do_violation scenario. The rule was correct about the world — a declared
        # prohibition with nothing testing it IS a coverage hole — and wrong about WHO it asked:
        # never_do_violation is held out, so it demanded work the submitter is forbidden to do.
        # There was no correct submission that declared a never-do list, and the only passing path
        # was to omit the list, which empties `ForgeInstructionSet.neverDo` and destroys the very
        # distinction that column was added to keep.
        #
        # **The refusal is not deleted. It moves to where the evidence is.** A declared entry is
        # recorded here as an outstanding obligation and carried onto the instruction set; whether
        # it was ever exercised is decided at scoring time by `never_do.is_never_do_coverage_hole`,
        # against SimForge's own held-out scenarios, and an unexercised obligation still blocks
        # full certification there. Submission time cannot answer that question — at submission the
        # scenarios that would answer it do not exist yet, which is why the check was unanswerable
        # rather than merely strict.
        nd_entries = list(module_never_do.get(mod, []))
        if nd_entries:
            never_do_obligations[mod] = nd_entries

        module_levels[mod] = classify_certification_level(
            classes_present,
            declared_not_applicable=module_declared_absences.get(mod, {}),
        )

    return CurriculumValidation(
        violations=violations,
        module_levels=module_levels,
        module_declared_absences=module_declared_absences,
        never_do_obligations=never_do_obligations,
    )


__all__ = [
    "ScenarioClass",
    "ALL_SCENARIO_CLASSES",
    "HELD_OUT_CLASSES",
    "REQUIRED_SCENARIO_FIELDS",
    "GATE_9_5_FLAG",
    "CERTIFICATION_LEVELS",
    "LEVEL_CERTIFIED",
    "LEVEL_CERTIFIED_WITH_DECLARED_ABSENCE",
    "LEVEL_DEMONSTRATED",
    "CurriculumValidation",
    "classify_certification_level",
    "validate_curriculum_submission",
]
