"""Operator CLI: grade one exam or one partition now, instead of at :20 or :50 (ADR-0167).

    apps/api/.venv/Scripts/python.exe -m scripts.grade_now --run-ref <ref> [--sitting <n>]
    apps/api/.venv/Scripts/python.exe -m scripts.grade_now --partition <id>

WHAT IT CALLS, AND WHY THE VERDICT IS THE SWEEP'S
=================================================

Exactly what the sweeps call, with what they pass:
- a Unit A ref: `submit_battery_result(session, ref, runtime=<examiner>, seed=0, sitting=n)`,
  as `sweep_unscored_runs` does for each run it picks, and only for a run it would pick;
- a partition: `examiner_runtime`, then `grade_partition(..., limit=PARTITION_SWEEP_LIMIT,
  budget_seconds=PARTITION_AGENT_BUDGET_SECONDS)`, as `sweep_sealed_partitions` does.

The runtime is the examiner's (`build_exam_runtime`): the pinned model, checked by digest before
anything is put, at the Village's declared settings for the Forge (cre-forge at 0.0), every call
from a clean cache (B135). Nothing in that reads the clock. So a verdict from here and one from a
sweep are the same rows, from the same inputs.

WHEN IT REFUSES, WRITING NOTHING
================================

- inside a sweep's window (:17-:24, :47-:54): the sweeps keep their slots;
- a sandbox run holds the machine's throwaway lock or a runner home's lock;
- Ollama has a model loaded: someone else is using it;
- under 8 GB free;
- the ref is not a run the :20 sweep would pick (open, Unit A, no verdict, current protocol),
  or the partition is not sealed;
- the sweep's own lock or the examiner's model lock (`exam:model`) is held.

A refusal is exit 2. An exam the examiner could not start from a clean cache (another phi4 user
appeared mid-exam) is exit 3: nothing is posted, the run stays unscored, and the next sweep grades
it as it would have.

Not a route, by design (ADR-0050): no request puts a held-out probe. It prints the ref, the
verdict and counts, never a probe or an answer.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.services.sandbox import rules

#: Exit codes. 0 graded, 2 refused before anything was put, 3 the exam refused (no clean cache).
GRADED, REFUSED, NO_CLEAN_CACHE = 0, 2, 3


class GradeRefused(Exception):
    """Nothing was put and nothing was written."""


@dataclass(frozen=True)
class Machine:
    """What `grade_now` reads about the machine before it grades. Injectable for the tests."""

    now: datetime
    free_gb: float
    #: who holds each sandbox lock that is held: the throwaway slot and every runner home named
    sandbox_held_by: tuple[str, ...] = ()
    #: the models Ollama has loaded right now
    loaded: tuple[str, ...] = ()


def sandbox_homes(extra: Sequence[str] = ()) -> list[Path]:
    """The runner homes to check: the default one, `SIMFORGE_SANDBOX_HOMES` (os.pathsep-separated)
    and any named on the command line."""
    from src.services.sandbox import runner

    named = [p for p in os.environ.get("SIMFORGE_SANDBOX_HOMES", "").split(os.pathsep) if p]
    homes = [runner.home(), *(Path(p) for p in (*named, *extra))]
    seen: list[Path] = []
    for h in homes:
        if h not in seen:
            seen.append(h)
    return seen


def measure(extra_homes: Sequence[str] = ()) -> Machine:
    """The real machine: the clock, free memory, the sandbox locks and Ollama's `/api/ps`."""
    from src.services.sandbox import runner

    held = []
    throwaway = runner.throwaway_lock().holder()
    if throwaway:
        held.append(f"the throwaway slot ({throwaway})")
    for h in sandbox_homes(extra_homes):
        who = runner.Lock(h).holder()  # a home keeps its run.lock at its root
        if who:
            held.append(f"runner home {h} ({who})")
    try:
        loaded = tuple(m.get("name", "?") for m in runner._ollama("/api/ps").get("models") or [])
    except Exception as exc:  # noqa: BLE001 - an Ollama that cannot be read cannot be checked
        raise GradeRefused(f"Ollama's /api/ps cannot be read: {type(exc).__name__}") from exc
    return Machine(datetime.now(), runner.free_gb(), tuple(held), loaded)


def check_machine(m: Machine) -> list[str]:
    """Every reason not to grade now. Empty means the machine is quiet."""
    found = []
    window = rules.in_sweep(m.now)
    if window is not None:
        found.append(f"inside the :{window[0]}-:{window[1]} sweep; the sweep keeps its slot")
    for who in m.sandbox_held_by:
        found.append(f"a sandbox run is active: {who}")
    if m.loaded:
        found.append(f"Ollama has {', '.join(m.loaded)} loaded: another user of the model")
    if m.free_gb < rules.MIN_FREE_GB:
        found.append(f"{m.free_gb:.1f} GB free, under {rules.MIN_FREE_GB:.0f} GB")
    return found


@dataclass
class Graded:
    what: str
    exit_code: int
    result: dict = field(default_factory=dict)


async def _the_sweeps_candidate(session, run_ref: str, sitting: int | None) -> int:  # noqa: ANN001
    """The sitting of `run_ref` the :20 sweep would grade, or a refusal. Read with the sweep's
    own selection, so this grades nothing the sweep would not."""
    from src.workers.battery_sweep import unscored_runs

    sittings = [r.sitting for r in await unscored_runs(session, limit=10**6) if r.runRef == run_ref]
    if not sittings:
        raise GradeRefused(
            f"{run_ref} is not a run the :20 sweep would grade "
            "(open, Unit A, no verdict, the current protocol)"
        )
    if sitting is not None:
        if sitting not in sittings:
            raise GradeRefused(f"{run_ref} has no unscored sitting {sitting}: {sorted(sittings)}")
        return sitting
    if len(sittings) > 1:
        raise GradeRefused(f"{run_ref} has unscored sittings {sorted(sittings)}: name one")
    return sittings[0]


async def grade_run(
    session,  # noqa: ANN001
    lock_session,  # noqa: ANN001
    run_ref: str,
    *,
    sitting: int | None = None,
    runtime=None,  # noqa: ANN001
) -> Graded:
    """One Unit A exam, as the :20 sweep grades it. The caller has checked the machine."""
    from src.models.operation_run import OperationRun
    from src.services.agent_runtime.llm_client import ColdStartFailed
    from src.services.agent_runtime.runtime import build_exam_runtime
    from src.services.operation.battery import BatterySkipped, submit_battery_result
    from src.services.village.reader import VillageReader, VillageReaderError
    from src.workers.battery_sweep import battery_sweep_lock
    from src.workers.exam_model_lock import exam_model_lock

    chosen = await _the_sweeps_candidate(session, run_ref, sitting)
    try:
        built = runtime or build_exam_runtime(VillageReader.from_settings())
    except VillageReaderError as exc:
        raise GradeRefused(f"the Village cannot be read: {exc}") from exc
    async with battery_sweep_lock(lock_session) as acquired:
        if not acquired:
            raise GradeRefused("a battery pass holds the sweep's lock; try again when it ends")
        async with exam_model_lock(lock_session) as model_free:
            if not model_free:
                raise GradeRefused("another exam holds the model (exam:model)")
            try:
                # The sweep's call, with the sweep's arguments (`sweep_unscored_runs`).
                out = await submit_battery_result(
                    session, run_ref, runtime=built, seed=0, sitting=chosen
                )
            except ColdStartFailed as exc:
                await session.rollback()
                return Graded(
                    run_ref,
                    NO_CLEAN_CACHE,
                    {"refused": "no_clean_cache", "detail": str(exc), "posted": False},
                )
    if isinstance(out, BatterySkipped):
        return Graded(run_ref, REFUSED, {"skipped": out.reason, "posted": False})
    from sqlalchemy import select

    session.expire_all()
    run = (
        await session.execute(
            select(OperationRun).where(
                OperationRun.runRef == run_ref, OperationRun.sitting == chosen
            )
        )
    ).scalar_one()
    return Graded(run_ref, GRADED, {"sitting": chosen, "verdict": run.verdict, "posted": True})


async def grade_partition_now(
    session,  # noqa: ANN001
    lock_session,  # noqa: ANN001
    partition_id: str,
    *,
    runtime=None,  # noqa: ANN001
) -> Graded:
    """One sealed partition, as the :50 sweep grades it. The caller has checked the machine."""
    from src.models.held_out_partition import HeldOutPartition
    from src.services.operation import partition_grading
    from src.services.village.reader import VillageReaderError
    from src.workers.exam_model_lock import exam_model_lock
    from src.workers.partition_sweep import (
        PARTITION_SWEEP_LIMIT,
        build_runtime,
        partition_sweep_lock,
    )

    partition = await session.get(HeldOutPartition, partition_id)
    if partition is None or partition.status != "sealed":
        raise GradeRefused(f"partition {partition_id!r} is not sealed; only a sealed one is sat")
    forge = partition.forgeId
    try:
        built = runtime or build_runtime()
    except VillageReaderError as exc:
        raise GradeRefused(f"the Village cannot be read: {exc}") from exc
    examiner = await partition_grading.examiner_runtime(built, forge_id=forge)
    if isinstance(examiner, str):
        raise GradeRefused(f"the examiner cannot sit: {examiner}")
    async with partition_sweep_lock(lock_session) as acquired:
        if not acquired:
            raise GradeRefused("a partition pass holds the sweep's lock; try again when it ends")
        async with exam_model_lock(lock_session) as model_free:
            if not model_free:
                raise GradeRefused("another exam holds the model (exam:model)")
            # The sweep's call, with the sweep's arguments (`sweep_sealed_partitions`).
            out = await partition_grading.grade_partition(
                session,
                partition_id,
                runtime=examiner,
                limit=PARTITION_SWEEP_LIMIT,
                budget_seconds=partition_grading.PARTITION_AGENT_BUDGET_SECONDS,
            )
    result = {"agents": out.agents, "put": out.put, "recorded": out.recorded}
    if out.skipped == partition_grading.SKIP_NO_CLEAN_CACHE:
        return Graded(partition_id, NO_CLEAN_CACHE, {**result, "refused": out.skipped})
    if out.skipped:
        return Graded(partition_id, REFUSED, {**result, "skipped": out.skipped})
    return Graded(partition_id, GRADED, result)


async def _run(args: argparse.Namespace, machine: Callable[[], Machine]) -> Graded:
    found = check_machine(machine())
    if found:
        raise GradeRefused("; ".join(found))
    from src.db import SessionLocal

    async with SessionLocal() as session, SessionLocal() as lock_session:
        if args.run_ref:
            return await grade_run(session, lock_session, args.run_ref, sitting=args.sitting)
        return await grade_partition_now(session, lock_session, args.partition)


def main(argv: list[str] | None = None, *, machine: Callable[[], Machine] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    what = p.add_mutually_exclusive_group(required=True)
    what.add_argument("--run-ref", help="a Unit A exam the :20 sweep would grade")
    what.add_argument("--partition", help="a sealed held-out partition")
    p.add_argument("--sitting", type=int, help="the sitting, when the ref has more than one")
    p.add_argument(
        "--sandbox-home", action="append", default=[], help="another runner home to check"
    )
    args = p.parse_args(argv)
    try:
        graded = asyncio.run(_run(args, machine or (lambda: measure(args.sandbox_home))))
    except GradeRefused as exc:
        print(f"refused, nothing graded: {exc}", file=sys.stderr)
        return REFUSED
    print(json.dumps({"graded": graded.what, **graded.result}, indent=2))
    return graded.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
