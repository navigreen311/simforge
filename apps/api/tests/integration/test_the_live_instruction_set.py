"""The live instruction set, and a partition that knows what it was authored from (ADR-0125).

1. The current instruction set is the one The Office last submitted, not the
   newest row. A re-authored hash that already exists becomes current.
2. A partition records the instruction hashes it was authored from. The grader
   refuses to grade it once they move, and re-sits a sitting sat under
   instructions that are no longer live.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.forge_instruction_set import ForgeInstructionSet
from src.models.held_out_partition import HeldOutPartition, HeldOutPartitionVerdict
from src.services.operation import held_out_partition as hp
from src.services.operation import partition_grading as pg
from src.services.operation.live_instructions import live_set
from src.services.operation.rubric import RESPONSE_PROTOCOL_VERSION
from src.utils.time import utcnow
from tests.integration.scheduler_path import fresh_session, run_scheduled
from tests.integration.test_held_out_isolation import FORGE as ISO_FORGE
from tests.integration.test_held_out_isolation import MODULE as ISO_MODULE
from tests.integration.test_held_out_isolation import _body
from tests.integration.test_operation_battery_run import (
    _examiner_pinned,  # noqa: F401 - autouse: pins the examiner for every test here
)
from tests.integration.test_partition_sweep import (
    AGENT,
    DIGEST,
    FORGE,
    ISET_HASH,
    MODULE,
    VENTURE,
    _seed,
    _serve,
)
from tests.unit.test_held_out_authoring import PORTFOLIO_HEALTH_NEVER_DO
from tests.unit.test_operation_battery import ScriptedProvider, _compliant

pytestmark = pytest.mark.asyncio


# --- ruling 1: the live set -----------------------------------------------------------


def _with_hash(h: str) -> dict:
    body = _body(list(PORTFOLIO_HEALTH_NEVER_DO))
    body["instruction_set_ref"]["content_hash"] = h
    return body


async def test_a_withdrawal_to_an_existing_hash_becomes_live(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """1.3.0 -> 1.4.0 -> back to 1.3.0's text: the last submission names the live set."""
    for h in ("sha256:v130", "sha256:v140", "sha256:v130"):
        res = await client.post("/api/operation/curriculum", json=_with_hash(h))
        assert res.status_code == 200, res.text

    async with fresh_session(db_session) as s:
        rows = (
            (
                await s.execute(
                    select(ForgeInstructionSet).where(ForgeInstructionSet.moduleId == ISO_MODULE)
                )
            )
            .scalars()
            .all()
        )
        live = await live_set(s, ISO_FORGE, ISO_MODULE)
    assert len(rows) == 2, "the withdrawal re-used the existing row"
    newest_row = max(rows, key=lambda r: r.createdAt)
    assert newest_row.contentHash == "sha256:v140", "the newest row is the withdrawn one"
    assert live is not None and live.contentHash == "sha256:v130", "but it is not live"


async def test_the_author_reads_the_live_set_not_the_newest_row(
    db_session: AsyncSession,
) -> None:
    now = utcnow()
    db_session.add_all(
        [
            ForgeInstructionSet(
                forgeId="f-live",
                moduleId="m",
                instructionVersion="1.3.0",
                forgeApiVersion="1",
                authoredBy="o",
                contentHash="live",
                neverDo=["Never retry after a timeout."],
                createdAt=now - timedelta(hours=2),
                lastSubmittedAt=now,
            ),
            ForgeInstructionSet(
                forgeId="f-live",
                moduleId="m",
                instructionVersion="1.4.0",
                forgeApiVersion="1",
                authoredBy="o",
                contentHash="withdrawn",
                neverDo=["Never delete the deal."],
                createdAt=now - timedelta(hours=1),
                lastSubmittedAt=now - timedelta(hours=1),
            ),
        ]
    )
    await db_session.commit()
    async with fresh_session(db_session) as s:
        assert await hp.current_never_do(s, "f-live") == {"m": ["Never retry after a timeout."]}
        assert await hp.current_hashes(s, "f-live") == {"m": "live"}


# --- ruling 2: the partition knows what it was authored from ----------------------------


async def test_a_new_partition_records_the_live_hashes(db_session: AsyncSession) -> None:
    db_session.add(
        ForgeInstructionSet(
            forgeId="f-auth",
            moduleId="m",
            instructionVersion="1",
            forgeApiVersion="1",
            authoredBy="o",
            contentHash="h-live",
            neverDo=["Never retry after a timeout."],
        )
    )
    await db_session.commit()
    async with fresh_session(db_session) as s:
        pid = await hp.author_partition(s, "v-auth", "f-auth", "Ivan Green")
    async with fresh_session(db_session) as s:
        assert (await s.get(HeldOutPartition, pid)).instructionHashes == {"m": "h-live"}


async def _verdicts(db: AsyncSession) -> list[HeldOutPartitionVerdict]:
    async with fresh_session(db) as s:
        return list((await s.execute(select(HeldOutPartitionVerdict))).scalars().all())


async def test_a_partition_whose_instructions_moved_is_not_graded(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A correct refusal would be matched against the wrong rule. Nothing is put."""
    pid = await _seed(db_session)
    db_session.add(
        ForgeInstructionSet(
            forgeId=FORGE,
            moduleId=MODULE,
            instructionVersion="9.9.9",
            forgeApiVersion="1",
            authoredBy="o",
            contentHash="sha256:moved",
            neverDo=list(PORTFOLIO_HEALTH_NEVER_DO),
            lastSubmittedAt=utcnow() + timedelta(minutes=1),
        )
    )
    await db_session.commit()
    provider = ScriptedProvider(_compliant)
    _serve(monkeypatch, provider)

    async with fresh_session(db_session) as s:
        out = await pg.grade_partition(s, pid, runtime=None)  # refused before any runtime use
    await run_scheduled("partition_sweep", db_session)

    assert out.skipped == pg.SKIP_INSTRUCTIONS_MOVED
    assert provider.prompts == [] and await _verdicts(db_session) == []


async def test_a_partition_that_never_recorded_its_instructions_is_not_graded(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = await _seed(db_session)
    async with fresh_session(db_session) as s:
        part = await s.get(HeldOutPartition, pid)
        part.instructionHashes = None
        await s.commit()
    provider = ScriptedProvider(_compliant)
    _serve(monkeypatch, provider)

    async with fresh_session(db_session) as s:
        out = await pg.grade_partition(s, pid, runtime=None)
    assert out.skipped == pg.SKIP_INSTRUCTIONS_UNRECORDED
    assert provider.prompts == []


async def test_a_sitting_under_instructions_no_longer_live_is_sat_again(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = await _seed(db_session)
    at = utcnow() - timedelta(hours=2)
    for verdict, when in (("IN_PROGRESS", at), ("PASS", at + timedelta(minutes=1))):
        db_session.add(
            HeldOutPartitionVerdict(
                partitionId=pid,
                ventureId=VENTURE,
                agentId=AGENT,
                verdict=verdict,
                partitionDigest=DIGEST,
                protocolVersion=RESPONSE_PROTOCOL_VERSION,
                instructionContentHash="sha256:not-live",
                decidedAt=when,
            )
        )
    await db_session.commit()
    provider = ScriptedProvider(_compliant)
    _serve(monkeypatch, provider)

    await run_scheduled("partition_sweep", db_session)

    rows = await _verdicts(db_session)
    assert provider.prompts, "re-sat"
    fresh = [r for r in rows if r.instructionContentHash not in (None, "sha256:not-live")]
    assert fresh and {r.instructionContentHash for r in fresh} == {ISET_HASH}


async def test_the_migration_backfills_from_recorded_submissions() -> None:
    sql = (
        Path(__file__).resolve().parents[4]
        / "packages"
        / "db"
        / "migrations"
        / "20260924220000_the_live_instruction_set"
        / "migration.sql"
    ).read_text(encoding="utf-8")
    assert '"lastSubmittedAt"' in sql and '"OperationScenarioSubmission"' in sql
    assert '"instructionHashes" JSONB' in sql
