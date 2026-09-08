"""Declared absence, and never-do coverage as one instance of it (Rev-2 audit FIX 2 + ADR-0049).

TWO LAYERS LIVE HERE, AND THE SECOND USED TO BE THE ONLY ONE
============================================================

`never_do_adherence` reports `not_applicable` in two OPPOSITE situations that must not be conflated:
  (a) the module declares NO never-do list  → genuinely not applicable (n/a is correct).
  (b) the module HAS a never-do list but the never_do_violation scenario was never run → a COVERAGE
      HOLE hiding as n/a. Per Rev 2 (every never-do entry needs a never_do_violation scenario), this
      is a coverage failure, NOT an n/a — and it blocks full certification.

The two are told apart by **a declaration**: `module_never_do` on the submission is what makes "this
module has no never-do rules" different from "somebody forgot". That mechanism was built, tested,
and applied to exactly one of the nine scenario classes.

ADR-0049 is the observation that the same distinction is needed for the other eight: the curriculum
validator asserts every module is the same shape, and they are not. A module that writes has
partial state, a retry hazard and a failure worth escalating; a module that does not write has
none of those. `capitalforge/portfolio_health` takes no identifier, writes nothing, and its
RETRY VS ESCALATE section reads "Retry freely." in full — there is nothing to hand a human, so
`escalation_required` has no honest content and no amount of effort will produce any.

So the general mechanism is stated first, and never-do is re-expressed as one instance of it.

WHAT THE GENERAL MECHANISM IS
=============================

A declared `not_applicable`, per class per module, **with a required prose reason**. Shaped on
`broker/compliance_couplings.NoFramework(why)` on The Office side, which solved the identical
problem: an empty list with a sentence attached, distinct from an empty list, because nothing can
tell an accidental empty from a considered one. **Four of nine rows there were accidental empties.**
That number is why the sentence is mandatory rather than encouraged.

Three properties, and they are the whole of it:

  1. The absence is STATED, not inferred. A class that is neither supplied nor declared
     not_applicable is still absent — `CLASS_ABSENT`, distinct from `CLASS_DECLARED_NOT_APPLICABLE`.
     A class nobody thought about must not read as "presumably fine".
  2. The reason is REQUIRED and it is prose. `NotApplicableDeclaration` refuses construction without
     one, at the point of construction, the way `NoFramework`'s `_validate` refuses at import.
  3. A declared not_applicable is NOT A PASS. It carries `VERDICT_NOT_APPLICABLE` and NO score —
     never a zero — the way the operation rubric already handles a dimension that does not apply.

WHAT THIS MODULE DELIBERATELY DOES NOT DECIDE
=============================================

**This is the primitive. It classifies; it does not enforce.** Which classes are mandatory, what a
declared n/a means for `classify_certification_level`, and whether a module carrying one can reach
`certified` at all are rulings that live in `services/operation/scenarios.py` and in ADR-0049, and
ADR-0049 leaves the certification-level question explicitly open. Nothing here refuses a submission.

**How a declaration arrives is settled elsewhere and this file only parses it.** Contract §10 A1.1
rules that a declared not_applicable travels as `module_not_applicable: dict[str, dict[str, str]]`
on `ForgeOperationCurriculum` — module → class → reason — and NOT as a scenario row, because a
statement about a (module, class) pair is not a scenario and a row would have needed an exemption
from every field §6 requires of one. `declarations_from_map` is the single place that map becomes
objects.

THE GAP THIS LEAVES IN THE NEVER-DO CASE, RECORDED RATHER THAN CLOSED
=====================================================================

Never-do's own declaration carries **no reason**. `STATUS_NONE` is reached by an absent or empty
`module_never_do` list — a declaration by empty collection, which is precisely the shape ADR-0049
argues is not enough, and precisely the shape `NoFramework` exists to replace. It is left exactly
as it was on purpose: every existing caller of `never_do_status` and `is_never_do_coverage_hole`
must be unable to tell that this file changed, and requiring a sentence there would change what
those callers see. Recorded here so the next author finds the inconsistency named rather than the
general rule quietly not applying to the case that motivated it.

This derives which case a result is in, from the persisted instruction-set never-do list + the
dimension's verdict. Pure where it can be; the list lookup touches the DB.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.forge_instruction_set import ForgeInstructionSet
from src.services.operation.rubric import VERDICT_NOT_APPLICABLE, VERDICT_NOT_RUN

NEVER_DO_DIMENSION = "never_do_adherence"

# Coverage status of one declared obligation against one result. Named for never-do because that is
# where they were born and every existing caller reads these strings; the meanings are general.
STATUS_NONE = "none"  # no obligation is declared → n/a is genuine
STATUS_TESTED = "tested"  # an obligation exists and the dimension was exercised (PASS/FAIL)
STATUS_UNTESTED = "untested"  # an obligation exists but the dimension is n/a / not-run → HOLE

# The state of one scenario class for one module. ADR-0049's "fourth outcome per class", minus the
# fourth: a declaration without a reason never becomes a state, because it is refused at
# construction and therefore cannot be classified.
CLASS_SUPPLIED = "supplied"  # a scenario of this class was submitted
CLASS_DECLARED_NOT_APPLICABLE = "declared_not_applicable"  # stated absent, with a reason
CLASS_ABSENT = "absent"  # neither supplied nor declared — nobody said anything


class NotApplicableDeclarationError(ValueError):
    """A declared absence that skips the sentence, or does not say what it is about.

    A `ValueError` so that callers already catching one keep working, and so that no layer above
    has to import this name to handle it.
    """


@dataclass(frozen=True, slots=True)
class NotApplicableDeclaration:
    """A declared absence: this module cannot exercise this scenario class, and here is why.

    An empty slot with a reason attached, distinct from an empty slot — nothing can tell an
    accidental absence from a considered one, which is the whole of ADR-0049 and the reason
    `NoFramework(why)` exists on The Office side.

    The reason is prose and it is required. `why` is refused when it is empty or whitespace, at
    construction, so a declaration without a sentence cannot reach a validator, a cert or a report.
    The canonical instance:

        NotApplicableDeclaration(
            module_id="portfolio_health",
            scenario_class="escalation_required",
            why="It takes no identifier, writes nothing, and its retry-vs-escalate section is "
                "'retry freely' in full. There is no failure to hand a human.",
        )
    """

    module_id: str
    scenario_class: str
    why: str

    def __post_init__(self) -> None:
        if not self.module_id.strip():
            raise NotApplicableDeclarationError(
                "a not_applicable declaration must name the module it is about"
            )
        if not self.scenario_class.strip():
            raise NotApplicableDeclarationError(
                f"module {self.module_id}: a not_applicable declaration must name the scenario "
                "class it declares absent"
            )
        if not self.why.strip():
            raise NotApplicableDeclarationError(
                f"module {self.module_id}: {self.scenario_class!r} declared not_applicable with no "
                "reason. An absence without a sentence is a claim that this class cannot apply "
                "here, and nothing can tell an accidental absence from a considered one."
            )


def index_declarations(
    declarations: Iterable[NotApplicableDeclaration],
) -> dict[str, dict[str, NotApplicableDeclaration]]:
    """module → class → declaration. Refuses the same class declared twice for one module.

    Two declarations for one slot are two different reasons for one absence, and nothing downstream
    could say which one the cert should carry. Refusing is the same discipline as `NoFramework`'s
    duplicate-flag check.
    """
    out: dict[str, dict[str, NotApplicableDeclaration]] = {}
    for decl in declarations:
        per_module = out.setdefault(decl.module_id, {})
        if decl.scenario_class in per_module:
            raise NotApplicableDeclarationError(
                f"module {decl.module_id}: {decl.scenario_class!r} declared not_applicable twice"
            )
        per_module[decl.scenario_class] = decl
    return out


def declarations_from_map(
    module_not_applicable: Mapping[str, Mapping[str, str]],
) -> dict[str, dict[str, NotApplicableDeclaration]]:
    """Parse the wire map (`ForgeOperationCurriculum.module_not_applicable`) into declarations.

    Contract §10 A1.1: a declared `not_applicable` travels as module → class → reason, NOT as a
    scenario row. This is the one place that map becomes objects, so the required-reason rule is
    applied identically whether a declaration arrived over the wire or was built in process — a
    reasonless entry raises `NotApplicableDeclarationError` here exactly as it does in the
    constructor.

    **The class NAME is not checked here.** Whether `scenario_class` is one of the nine is the
    curriculum validator's rejection to make (§1), and it lives in `scenarios.py`. This function
    parses a declaration; it does not rule on one.
    """
    return index_declarations(
        NotApplicableDeclaration(module_id=module_id, scenario_class=scenario_class, why=why)
        for module_id, per_module in module_not_applicable.items()
        for scenario_class, why in per_module.items()
    )


def classify_scenario_class(
    scenario_class: str,
    *,
    supplied_classes: Iterable[str],
    declarations: Mapping[str, NotApplicableDeclaration],
) -> str:
    """Which of the three states one scenario class is in, for one module.

    `declarations` is one module's declarations keyed by class — i.e. one value out of
    `declarations_from_map(...)`, or `{}` for a module that declared nothing. **This classifies and
    stops.**
    Whether `CLASS_ABSENT` is a rejection, a label, or nothing at all depends on which classes are
    mandatory — a ruling that lives in the curriculum validator, not here.
    """
    if scenario_class in set(supplied_classes):
        return CLASS_SUPPLIED
    if scenario_class in declarations:
        return CLASS_DECLARED_NOT_APPLICABLE
    return CLASS_ABSENT


def not_applicable_class_result(declaration: NotApplicableDeclaration) -> dict[str, str]:
    """What a declared absence carries to the cert: `not_applicable`, and NO score.

    There is no `score` key, deliberately — not `0.0`, not `None`-with-a-key. A declared n/a is not
    a pass and it is not a failure; a zero would be a claim about the agent, and averaging one is
    the mistake the domain rubric made and the operation rubric was built to refuse.
    """
    return {
        "scenario_class": declaration.scenario_class,
        "verdict": VERDICT_NOT_APPLICABLE,
    }


def dimension_verdict(results: list[dict], dimension: str) -> str | None:
    """The verdict recorded for one rubric dimension, or None when it is not present at all."""
    for r in results:
        if r.get("dimension") == dimension:
            return r.get("verdict")
    return None


def coverage_status(*, obligation_declared: bool, verdict: str | None) -> str:
    """Classify one declared obligation's coverage: none / tested / untested.

    The general form of `never_do_status`. An obligation nobody declared is genuinely n/a. One that
    is declared and whose dimension reports n/a, NOT_RUN, or nothing at all was not exercised — and
    an unexercised obligation is a coverage hole wearing an n/a, not an n/a.
    """
    if not obligation_declared:
        return STATUS_NONE  # genuinely not applicable — n/a is correct, no penalty
    if verdict in (None, VERDICT_NOT_APPLICABLE, VERDICT_NOT_RUN):
        return STATUS_UNTESTED  # declared but the dimension wasn't exercised → coverage hole
    return STATUS_TESTED


async def module_never_do_lists(session: AsyncSession) -> dict[tuple[str, str], list[str]]:
    """Every (forge, module) → its declared never-do list (from any instruction set that carries
    one). Absent or empty ⇒ the module has no never-do rules."""
    out: dict[tuple[str, str], list[str]] = {}
    for iset in (await session.execute(select(ForgeInstructionSet))).scalars().all():
        key = (iset.forgeId, iset.moduleId)
        if iset.neverDo and not out.get(key):
            out[key] = list(iset.neverDo)
    return out


async def module_never_do_list(session: AsyncSession, forge_id: str, module_id: str) -> list[str]:
    return (await module_never_do_lists(session)).get((forge_id, module_id), [])


def never_do_status(has_never_do_list: bool, results: list[dict]) -> str:
    """Classify the never-do coverage of one operation result.

    One instance of `coverage_status`: the declared obligation is the module's never-do list, and
    the dimension that exercises it is `never_do_adherence`. Behaviour is unchanged from before the
    generalisation — this is the same two-branch decision, named once instead of twice.
    """
    return coverage_status(
        obligation_declared=has_never_do_list,
        verdict=dimension_verdict(results, NEVER_DO_DIMENSION),
    )


def is_never_do_coverage_hole(has_never_do_list: bool, results: list[dict]) -> bool:
    """A required never-do dimension went untested → blocks full certification (FIX 2)."""
    return never_do_status(has_never_do_list, results) == STATUS_UNTESTED
