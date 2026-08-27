"""Never-do coverage derivation (Rev-2 audit FIX 2).

`never_do_adherence` reports `not_applicable` in two OPPOSITE situations that must not be conflated:
  (a) the module declares NO never-do list  → genuinely not applicable (n/a is correct).
  (b) the module HAS a never-do list but the never_do_violation scenario was never run → a COVERAGE
      HOLE hiding as n/a. Per Rev 2 (every never-do entry needs a never_do_violation scenario), this
      is a coverage failure, NOT an n/a — and it blocks full certification.

This derives which case a result is in, from the persisted instruction-set never-do list + the
dimension's verdict. Pure where it can be; the list lookup touches the DB.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.forge_instruction_set import ForgeInstructionSet
from src.services.operation.rubric import VERDICT_NOT_APPLICABLE, VERDICT_NOT_RUN

NEVER_DO_DIMENSION = "never_do_adherence"

# Per-cert never-do coverage status.
STATUS_NONE = "none"  # module declares no never-do list → n/a is genuine
STATUS_TESTED = "tested"  # list exists and the dimension was actually exercised (PASS/FAIL)
STATUS_UNTESTED = "untested"  # list exists but the dimension is n/a / not-run → COVERAGE HOLE


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


def _never_do_verdict(results: list[dict]) -> str | None:
    for r in results:
        if r.get("dimension") == NEVER_DO_DIMENSION:
            return r.get("verdict")
    return None


def never_do_status(has_never_do_list: bool, results: list[dict]) -> str:
    """Classify the never-do coverage of one operation result."""
    if not has_never_do_list:
        return STATUS_NONE  # genuinely not applicable — n/a is correct, no penalty
    verdict = _never_do_verdict(results)
    if verdict in (None, VERDICT_NOT_APPLICABLE, VERDICT_NOT_RUN):
        return STATUS_UNTESTED  # list exists but the dimension wasn't exercised → coverage hole
    return STATUS_TESTED


def is_never_do_coverage_hole(has_never_do_list: bool, results: list[dict]) -> bool:
    """A required never-do dimension went untested → blocks full certification (FIX 2)."""
    return never_do_status(has_never_do_list, results) == STATUS_UNTESTED
