"""The partition's three tables exist in both schemas, and a row survives a fresh session.

ADR-0108. The suite builds its database from the SQLAlchemy mirror, so a table missing
from schema.prisma or the migrations would pass everything else. This reads both files.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import select

from src.models.held_out_partition import (
    PARTITION_VERDICTS,
    HeldOutPartition,
    HeldOutPartitionScenario,
    HeldOutPartitionVerdict,
)
from tests.integration.scheduler_path import fresh_session

REPO = Path(__file__).resolve().parents[4]
SCHEMA = REPO / "packages" / "db" / "schema.prisma"
MIGRATION = (
    REPO / "packages" / "db" / "migrations" / "20260923120000_the_held_out_partition"
)
TABLES = ("HeldOutPartition", "HeldOutPartitionScenario", "HeldOutPartitionVerdict")


def test_prisma_declares_all_three() -> None:
    text = SCHEMA.read_text(encoding="utf-8")
    for table in TABLES:
        assert re.search(rf"^model {table} \{{", text, re.M), f"{table} not in schema.prisma"


def test_the_migration_creates_all_three() -> None:
    sql = (MIGRATION / "migration.sql").read_text(encoding="utf-8")
    for table in TABLES:
        assert f'CREATE TABLE IF NOT EXISTS "{table}"' in sql


def test_the_migration_checks_the_same_verdicts_the_model_names() -> None:
    sql = (MIGRATION / "migration.sql").read_text(encoding="utf-8")
    check = re.search(r'"verdict" IN \(([^)]*)\)', sql)
    assert check
    assert {v.strip(" '") for v in check.group(1).split(",")} == set(PARTITION_VERDICTS)


def test_no_verdict_table_carries_a_reason() -> None:
    """Whether, never why. A reason column is the first step to a read path."""
    cols = set(HeldOutPartitionVerdict.__table__.columns.keys())
    assert not cols & {"reason", "why", "detail", "failedScenarios", "evidence"}


async def test_rows_survive_a_fresh_session(db_session) -> None:
    part = HeldOutPartition(ventureId="v-1", forgeId="cre-forge", authoredBy="ops")
    db_session.add(part)
    await db_session.flush()
    db_session.add(
        HeldOutPartitionScenario(
            partitionId=part.id,
            moduleId="buyer_match",
            scenarioClass="never_do_violation",
            body={"situation": "x"},
            digest="d1",
        )
    )
    db_session.add(
        HeldOutPartitionVerdict(
            partitionId=part.id,
            ventureId="v-1",
            agentId="a-1",
            verdict="FAIL",
            partitionDigest="pd",
        )
    )
    await db_session.commit()

    async with fresh_session(db_session) as s:
        got = (await s.execute(select(HeldOutPartition))).scalar_one()
        assert got.status == "authoring"
        n = (await s.execute(select(HeldOutPartitionScenario))).scalars().all()
        v = (await s.execute(select(HeldOutPartitionVerdict))).scalar_one()
        assert len(n) == 1 and v.verdict == "FAIL"
