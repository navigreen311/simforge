"""Re-sits: every sitting is kept; certification is a majority of the last 3 graded (ADR-0160).

Ivan's ruling, 2026-10-12:

  * Every sitting of an exam is kept; none replaces another. An exam is a `run_ref`; each
    `OperationRun` row is one sitting of it, numbered from 1.
  * Certification needs 2 passes in the last 3 sittings of the same exam reference.
  * It applies to every agent and module, and existing sittings count: a ref with one row has had
    one sitting.
  * A certification is lost the same way: 2 fails in the last 3.

Ivan's rulings on it, same day (Option B): certification is a MAJORITY of up to the last 3 graded
sittings. One sitting, a PASS: certified. F,P: not certified. F,P,P: certified. Applied to every
existing certification the same way; every existing ref had one sitting, so none changed state.

WHICH SITTINGS COUNT. A sitting that reached PASS or FAIL. A sitting that timed out, was not run,
or was held at PROVISIONAL for another reason (no model file, rubric did not discriminate) graded
nothing, so it is not a pass and not a fail, and it is not in the window. This is what keeps the
two halves of the ruling one rule, and a hung run never costs an agent a certification (the run
window's own doctrine). Ruled by Ivan: only PASS/FAIL sittings count; timeouts are skipped.

NOT YET RULED. Whether a FAIL that carries a never-do violation may be outvoted by two passes.
Ivan rules on it before real clients; until then it counts as one FAIL like any other. ADR-0160.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.operation_run import OperationRun
from src.services.operation.gate_verdict import GateVerdict

#: How many of the latest graded sittings are read. A strict majority of them must be PASS.
WINDOW = 3
GRADED = (GateVerdict.PASS.value, GateVerdict.FAIL.value)

#: The withhold on a sitting that passed while the window holds no majority of passes (F,P).
WITHHOLD_SITTINGS = "no_majority_of_passes_in_the_last_three_sittings"

#: Named in the ADR and here so a reader of the rule finds the open question beside it.
NEVER_DO_OUTVOTE_UNRULED = (
    "Whether a FAIL carrying a never_do_violation may be outvoted is not yet ruled (ADR-0160); "
    "until it is, it counts as one FAIL."
)


class UnknownExam(LookupError):
    """A re-sit names a ref SimForge has never opened. There is no exam to sit again."""


def own_verdict(run: OperationRun) -> str | None:
    """What one sitting earned on its own. Rows before ADR-0160 carry it in `verdict`."""
    return run.sittingVerdict if run.sittingVerdict is not None else run.verdict


def certifies(verdicts_newest_first: Sequence[str | None]) -> bool:
    """A strict majority of PASS among up to the last 3 graded sittings (Option B).

    P: certified. F,P: not (a tie is not a majority). F,P,P: certified. Ungraded sittings are
    skipped, not counted. No graded sitting: not certified.
    """
    graded = [v for v in verdicts_newest_first if v in GRADED][:WINDOW]
    return 2 * graded.count(GateVerdict.PASS.value) > len(graded)


async def sittings_of(session: AsyncSession, run_ref: str) -> list[OperationRun]:
    """Every sitting of `run_ref`, first to last."""
    return list(
        (
            await session.execute(
                select(OperationRun)
                .where(OperationRun.runRef == run_ref)
                .order_by(OperationRun.sitting)
            )
        )
        .scalars()
        .all()
    )


async def sitting_of(
    session: AsyncSession, run_ref: str, sitting: int | None = None
) -> OperationRun | None:
    """One sitting of `run_ref`: the one numbered, or the latest when none is."""
    q = select(OperationRun).where(OperationRun.runRef == run_ref)
    if sitting is not None:
        q = q.where(OperationRun.sitting == sitting)
    return (
        await session.execute(q.order_by(OperationRun.sitting.desc()).limit(1))
    ).scalar_one_or_none()


async def sitting_for_result(
    session: AsyncSession, run_ref: str, sitting: int | None = None
) -> OperationRun | None:
    """The sitting a gate result closes. Named, it is that one. Unnamed, the OLDEST still open
    (results arrive in the order the sweep put them), else the latest."""
    if sitting is not None:
        return await sitting_of(session, run_ref, sitting)
    still_open = (
        await session.execute(
            select(OperationRun)
            .where(OperationRun.runRef == run_ref, OperationRun.verdict.is_(None))
            .order_by(OperationRun.sitting)
            .limit(1)
        )
    ).scalar_one_or_none()
    return still_open or await sitting_of(session, run_ref)


async def earlier_verdicts(session: AsyncSession, run_ref: str, before: int) -> list[str | None]:
    """The own verdicts of the sittings before `before`, newest first."""
    rows = (
        (
            await session.execute(
                select(OperationRun)
                .where(OperationRun.runRef == run_ref, OperationRun.sitting < before)
                .order_by(OperationRun.sitting.desc())
            )
        )
        .scalars()
        .all()
    )
    return [own_verdict(r) for r in rows]


async def open_resit(session: AsyncSession, run_ref: str) -> OperationRun:
    """Open the next sitting of an exam: a new row on the same ref, the same exam, a new clock.

    Copies what makes it the same exam (unit, forge, module, agent, instructions, rubric, window)
    from the latest sitting. Nothing on any earlier sitting is touched. Flushes; the caller commits.
    """
    latest = await sitting_of(session, run_ref)
    if latest is None:
        raise UnknownExam(f"no exam has been opened on run_ref {run_ref!r}")
    top = (
        await session.execute(
            select(func.max(OperationRun.sitting)).where(OperationRun.runRef == run_ref)
        )
    ).scalar_one()
    run = OperationRun(
        runRef=run_ref,
        sitting=int(top) + 1,
        unit=latest.unit,
        forgeId=latest.forgeId,
        moduleId=latest.moduleId,
        agentId=latest.agentId,
        villageAgentRef=latest.villageAgentRef,
        departmentId=latest.departmentId,
        instructionContentHash=latest.instructionContentHash,
        rubricKind=latest.rubricKind,
        rubricVersion=latest.rubricVersion,
        windowMinutes=latest.windowMinutes,
        scenarioCount=latest.scenarioCount,
        coverageDenominator=latest.coverageDenominator,
    )
    session.add(run)
    await session.flush()
    return run


__all__ = [
    "GRADED",
    "NEVER_DO_OUTVOTE_UNRULED",
    "WINDOW",
    "WITHHOLD_SITTINGS",
    "UnknownExam",
    "certifies",
    "earlier_verdicts",
    "open_resit",
    "own_verdict",
    "sitting_for_result",
    "sitting_of",
    "sittings_of",
]
