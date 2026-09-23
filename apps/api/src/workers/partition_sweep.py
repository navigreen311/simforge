"""The partition sweep: grade every sealed held-out partition that has an agent due (ADR-0110).

WHY A SWEEP AND NOT AN ENDPOINT
===============================

ADR-0050: no request handler may put a held-out probe to an agent. A partition
is the most held-out content SimForge has, so grading it is reached only from
the scheduler. `jobs.partition_sweep` refuses a request-path call (a session
handed in by the trigger route) before it touches anything.

WHAT IT DOES NOT DO
===================

It decides no verdict - `partition_grading.grade_partition` does, one agent at
a time, and appends one row per verdict. It returns counts, never verdicts or
reasons, because the scheduler logs what a job returns.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.held_out_partition import HeldOutPartition
from src.services.agent_runtime.llm_client import provider_label
from src.services.agent_runtime.runtime import AgentRuntime, build_exam_runtime
from src.services.operation import partition_grading
from src.services.village.reader import VillageReader, VillageReaderError
from src.telemetry.logging import get_logger

log = get_logger("partition_sweep")

JOB_NAME = "partition_sweep"

#: Agents PUT per pass - the paid part. A partition probe is a live model call.
PARTITION_SWEEP_LIMIT = 10

#: Its own key: a second concurrent pass would put the same agent twice.
LOCK_KEY = "sweep:partition"

SKIP_VILLAGE = "village_data_unavailable"
SKIP_LOCKED = "another_pass_holds_the_lock"
SKIP_REQUEST_PATH = "scheduler_only_see_adr_0050"


@asynccontextmanager
async def partition_sweep_lock(session: AsyncSession) -> AsyncIterator[bool]:
    """This sweep's advisory lock, pinned to one connection. True off Postgres.

    The same construction as `battery_sweep_lock` and for the same reasons
    (ADR-0057): session-scoped lock, one connection, bound parameter.
    """
    conn = await session.connection()
    if conn.dialect.name != "postgresql":
        yield True
        return
    got = await conn.execute(text("SELECT pg_try_advisory_lock(hashtext(:key))"), {"key": LOCK_KEY})
    acquired = bool(got.scalar())
    try:
        yield acquired
    finally:
        if acquired:
            await conn.execute(text("SELECT pg_advisory_unlock(hashtext(:key))"), {"key": LOCK_KEY})


def build_runtime() -> AgentRuntime:
    """The examiner's runtime (ADR-0061). Raises `VillageReaderError` with no Village.

    A named seam: a test replaces THIS, on this module, and everything after
    it - the examiner check, the grading, the rows - runs for real.
    """
    return build_exam_runtime(VillageReader.from_settings())


@dataclass(frozen=True, slots=True)
class SweepOutcome:
    """Counts only. This module decides no outcome and reports no verdict."""

    partitions: int
    agents: int
    put: int
    recorded: int
    skipped: str | None = None


async def sealed_partition_ids(session: AsyncSession) -> list[str]:
    """Every sealed partition, oldest seal first. Authoring and retired never."""
    rows = await session.execute(
        select(HeldOutPartition.id)
        .where(HeldOutPartition.status == "sealed")
        .order_by(HeldOutPartition.sealedAt, HeldOutPartition.id)
    )
    return list(rows.scalars().all())


async def sweep_sealed_partitions(
    session: AsyncSession,
    *,
    runtime: AgentRuntime,
    limit: int = PARTITION_SWEEP_LIMIT,
    seed: int = 0,
) -> SweepOutcome:
    """Check the examiner once, then grade each sealed partition in turn.

    An examiner that cannot sit the exam puts nothing and writes nothing:
    the partitions read NOT_RUN through the verdict endpoint, which is true.
    One failing partition does not end the pass.
    """
    examiner = await partition_grading.examiner_runtime(runtime)
    if isinstance(examiner, str):
        log.warning("partition_sweep_refused_examiner", reason=examiner)
        return SweepOutcome(0, 0, 0, 0, skipped=examiner)

    ids = await sealed_partition_ids(session)
    agents = put = recorded = 0
    for pid in ids:
        remaining = limit - put
        if remaining <= 0:
            break
        try:
            out = await partition_grading.grade_partition(
                session,
                pid,
                runtime=examiner,
                seed=seed,
                limit=remaining,
                budget_seconds=partition_grading.PARTITION_AGENT_BUDGET_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001 - one partition must not end the pass
            await session.rollback()
            log.warning("partition_sweep_partition_failed", partition=pid, error=type(exc).__name__)
            continue
        agents += out.agents
        put += out.put
        recorded += out.recorded
    return SweepOutcome(len(ids), agents, put, recorded)


async def run_partition_pass(session: AsyncSession, lock_session: AsyncSession) -> dict:
    """One scheduled pass. The lock gets its own session, as `battery_sweep`'s does."""
    try:
        runtime = build_runtime()
    except VillageReaderError as exc:
        log.warning("partition_sweep_skipped", error=str(exc))
        return {"job": JOB_NAME, "skipped": SKIP_VILLAGE}
    async with partition_sweep_lock(lock_session) as acquired:
        if not acquired:
            return {"job": JOB_NAME, "skipped": SKIP_LOCKED}
        outcome = await sweep_sealed_partitions(session, runtime=runtime)
    result = {
        "job": JOB_NAME,
        "examiner": provider_label(runtime.provider),
        "partitions": outcome.partitions,
        "agents": outcome.agents,
        "put": outcome.put,
        "recorded": outcome.recorded,
    }
    if outcome.skipped:
        result["skipped"] = outcome.skipped
    return result
