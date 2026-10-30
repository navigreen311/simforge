"""One sealed partition per venture and forge (ADR-0163, B96).

ADR-0113 held one per venture, so sealing one forge's partition retired another forge's. These
hold the narrowed rule at the seal, in the database and at Gate 9.5:

1. Two forges stay sealed side by side; a seal retires its own forge's earlier seal only.
2. The race is still refused, per venture and forge.
3. Gate 9.5 asked for a forge reads that forge's partition, with six keys. Asked for the
   venture alone, four keys, the weakest across its forges.

Every seal assertion reads the row back from a fresh session.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_session
from src.main import create_app
from src.models.base import _new_id
from src.models.held_out_partition import (
    HeldOutPartition,
    HeldOutPartitionSeal,
    HeldOutPartitionVerdict,
)
from src.services.operation import held_out_partition as hp
from src.services.operation.partition_roster import roster_digest
from src.services.operation.partition_verdict import (
    FORGE_RESPONSE_KEYS,
    RESPONSE_KEYS,
    venture_verdict,
)
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION, PARTITION_PROTOCOL_VERSION
from tests.integration.operators import credential_of, ensure
from tests.integration.scheduler_path import fresh_session
from tests.integration.test_partition_authoring import FORGE, VENTURE, _seed

#: Seeded by `_seed` beside FORGE, with a never-do list of its own.
OTHER_FORGE = "other-forge"
AUTHOR = "Ivan Green"
SEALER = "Grace Hopper"
REPO = Path(__file__).resolve().parents[4]
MIGRATION = (
    REPO / "packages" / "db" / "migrations" / "20261029120000_one_sealed_per_venture_and_forge"
)
TOKEN = "office-tenant-token-for-tests"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
URL = "/office/gate_9_5_verdict"
T0 = datetime(2026, 10, 29, 12, 0, 0)


async def _author(db: AsyncSession, forge: str = FORGE) -> str:
    async with fresh_session(db) as s:
        await ensure(s, AUTHOR)
        return await hp.author_partition(
            s, VENTURE, forge, AUTHOR, credential=credential_of(AUTHOR)
        )


async def _seal(db: AsyncSession, pid: str, by: str = SEALER) -> str:
    async with fresh_session(db) as s:
        await ensure(s, by)
        return await hp.seal_partition(s, pid, by, credential=credential_of(by))


async def _status(db: AsyncSession, pid: str) -> str:
    async with fresh_session(db) as s:
        row = await s.get(HeldOutPartition, pid)
        assert row is not None
        return row.status


async def _retired_by(db: AsyncSession, pid: str) -> list[str]:
    async with fresh_session(db) as s:
        seal = (
            await s.execute(
                select(HeldOutPartitionSeal).where(HeldOutPartitionSeal.partitionId == pid)
            )
        ).scalar_one()
        return list(seal.retiredPartitionIds)


# --- 1. the seal ------------------------------------------------------------------------------


async def test_two_forges_stay_sealed_side_by_side(db_session: AsyncSession) -> None:
    """B96's case: one venture, two forges. The second seal retires nothing."""
    await _seed(db_session)
    capital = await _author(db_session, FORGE)
    other = await _author(db_session, OTHER_FORGE)
    await _seal(db_session, capital)
    await _seal(db_session, other)

    assert await _status(db_session, capital) == "sealed"
    assert await _status(db_session, other) == "sealed"
    assert await _retired_by(db_session, other) == []


async def test_a_seal_still_retires_its_own_forges_earlier_seal(db_session: AsyncSession) -> None:
    await _seed(db_session)
    first = await _author(db_session, FORGE)
    other = await _author(db_session, OTHER_FORGE)
    second = await _author(db_session, FORGE)
    await _seal(db_session, first)
    await _seal(db_session, other)
    await _seal(db_session, second, "Katherine Johnson")

    assert await _status(db_session, first) == "retired"
    assert await _status(db_session, second) == "sealed"
    # Control: the other forge's seal is untouched by the reseal.
    assert await _status(db_session, other) == "sealed"
    assert await _retired_by(db_session, second) == [first]


# --- 2. the database, and the race ------------------------------------------------------------


def _sealed(forge: str, venture: str = "v-db") -> HeldOutPartition:
    return HeldOutPartition(
        ventureId=venture,
        forgeId=forge,
        status="sealed",
        authoredBy="ivan",
        sealedBy=SEALER,
        contentDigest="d",
    )


async def test_the_database_holds_one_sealed_partition_per_venture_and_forge(
    db_session: AsyncSession,
) -> None:
    db_session.add_all([_sealed(FORGE), _sealed(OTHER_FORGE)])
    await db_session.commit()
    db_session.add(_sealed(FORGE))
    with pytest.raises(IntegrityError) as caught:
        await db_session.commit()
    await db_session.rollback()
    # What the seal reads to tell a lost race from another refusal.
    assert hp._lost_the_race(caught.value)


async def test_a_seal_that_loses_the_race_for_its_forge_is_refused(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two seals of one forge racing. The loser's retire step saw nothing; the index decides."""
    await _seed(db_session)
    winner = await _author(db_session, FORGE)
    loser = await _author(db_session, FORGE)
    await _seal(db_session, winner)

    async def _saw_nothing(session, venture_id, forge_id, *, keep):
        return []

    monkeypatch.setattr(hp, "_retire_sealed", _saw_nothing)
    with pytest.raises(hp.PartitionRefused, match="committed first"):
        await _seal(db_session, loser, "Katherine Johnson")

    assert await _status(db_session, winner) == "sealed"
    assert await _status(db_session, loser) == "authoring"


def test_the_migration_builds_the_new_index_before_dropping_the_old() -> None:
    sql = (MIGRATION / "migration.sql").read_text(encoding="utf-8")
    create = sql.index(
        'CREATE UNIQUE INDEX IF NOT EXISTS "HeldOutPartition_one_sealed_per_venture_forge"'
    )
    drop = sql.index('DROP INDEX IF EXISTS "HeldOutPartition_one_sealed_per_venture";')
    assert create < drop
    assert '("ventureId", "forgeId") WHERE "status" = \'sealed\'' in sql
    # Nothing is rewritten: a partition retired by another forge's seal stays retired.
    assert "UPDATE" not in sql.upper()


# --- 3. Gate 9.5 ------------------------------------------------------------------------------


@pytest_asyncio.fixture
async def bridged(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncClient, None]:
    monkeypatch.setattr(settings, "office_tenant_token", TOKEN)
    app = create_app()

    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _partition(venture: str, forge: str, *, status: str = "sealed") -> HeldOutPartition:
    row = HeldOutPartition(
        ventureId=venture,
        forgeId=forge,
        status=status,
        authoredBy="ivan",
        contentDigest=f"sha256:{forge}",
        sealedAt=T0,
        sealedBy=SEALER,
    )
    row.id = _new_id()
    return row


def _verdict(
    p: HeldOutPartition, agent: str, verdict: str, *, at: datetime = T0
) -> HeldOutPartitionVerdict:
    return HeldOutPartitionVerdict(
        partitionId=p.id,
        ventureId=p.ventureId,
        agentId=agent,
        verdict=verdict,
        partitionDigest=p.contentDigest,
        protocolVersion=PARTITION_PROTOCOL_VERSION,
        rubricVersion=OPERATION_RUBRIC_VERSION,
        decidedAt=at,
    )


async def _add(session: AsyncSession, *rows: object) -> None:
    for row in rows:
        session.add(row)
        await session.flush()
    await session.commit()


async def _two_forges(db: AsyncSession) -> tuple[HeldOutPartition, HeldOutPartition]:
    """B96 as measured: one forge PASSes, the other FAILs."""
    passing = _partition("v-two", FORGE)
    failing = _partition("v-two", OTHER_FORGE)
    await _add(db, passing, failing)
    await _add(
        db,
        _verdict(passing, "a1", "PASS", at=T0 + timedelta(hours=1)),
        _verdict(failing, "a2", "FAIL", at=T0),
    )
    return passing, failing


async def test_asked_for_a_forge_the_answer_is_that_forges_partition(
    bridged: AsyncClient, db_session: AsyncSession
) -> None:
    passing, failing = await _two_forges(db_session)

    res = await bridged.post(URL, json={"venture_id": "v-two", "forge_id": FORGE}, headers=AUTH)
    assert res.status_code == 200, res.text
    body = res.json()
    assert list(body) == list(FORGE_RESPONSE_KEYS)
    assert body == {
        "venture_id": "v-two",
        "forge_id": FORGE,
        "partition_exists": True,
        "partition_id": passing.id,
        "verdict": "PASS",
        "decided_at": "2026-10-29T13:00:00+00:00",
    }
    # Another forge's FAIL is not read. Control: asked for that forge, it is.
    other = (
        await bridged.post(URL, json={"venture_id": "v-two", "forge_id": OTHER_FORGE}, headers=AUTH)
    ).json()
    assert (other["partition_id"], other["verdict"]) == (failing.id, "FAIL")


async def test_asked_without_a_forge_four_keys_and_the_weakest_forge(
    bridged: AsyncClient, db_session: AsyncSession
) -> None:
    await _two_forges(db_session)
    res = await bridged.post(URL, json={"venture_id": "v-two"}, headers=AUTH)
    assert res.status_code == 200, res.text
    body = res.json()
    assert list(body) == list(RESPONSE_KEYS)
    assert body == {
        "venture_id": "v-two",
        "partition_exists": True,
        "verdict": "FAIL",
        "decided_at": "2026-10-29T12:00:00+00:00",
    }


async def test_a_venture_with_one_sealed_partition_reads_as_it_always_did(
    db_session: AsyncSession,
) -> None:
    p = _partition("v-one", FORGE)
    await _add(db_session, p)
    await _add(db_session, _verdict(p, "a1", "PASS"))
    async with fresh_session(db_session) as s:
        v1 = await venture_verdict(s, "v-one")
        v2 = await venture_verdict(s, "v-one", FORGE)
    assert v1 == {
        "venture_id": "v-one",
        "partition_exists": True,
        "verdict": "PASS",
        "decided_at": "2026-10-29T12:00:00+00:00",
    }
    assert {k: v2[k] for k in RESPONSE_KEYS} == v1


async def test_a_forge_with_no_sealed_partition_reads_as_absent(
    bridged: AsyncClient, db_session: AsyncSession
) -> None:
    """A retired partition, an unsealed forge and an unknown forge read alike."""
    retired = _partition("v-r", FORGE, status="retired")
    await _add(db_session, retired, _partition("v-r", OTHER_FORGE))
    await _add(db_session, _verdict(retired, "a1", "PASS"))

    for forge in (FORGE, "never-heard-of"):
        body = (
            await bridged.post(URL, json={"venture_id": "v-r", "forge_id": forge}, headers=AUTH)
        ).json()
        assert body == {
            "venture_id": "v-r",
            "forge_id": forge,
            "partition_exists": False,
            "partition_id": None,
            "verdict": None,
            "decided_at": None,
        }


async def test_each_forge_is_read_by_its_own_recorded_roster(db_session: AsyncSession) -> None:
    """ADR-0162 under ADR-0163: the roster binds per partition, so per forge.

    One forge's roster holds and names only a1, so a9's FAIL there is not read. The other
    forge's roster was edited after its seal, so it answers NOT_RUN. v1 names the weaker.
    """

    def _roster(agent: str) -> dict:
        grant = {"grant_id": f"g-{agent}", "agent_id": agent, "module_id": "m"}
        return {"stated_at": "2026-10-29T00:00:00+00:00", "grants": [grant]}

    held = _partition("v-rost", FORGE)
    held.roster = _roster("a1")
    held.rosterDigest = roster_digest(held.roster)
    moved = _partition("v-rost", OTHER_FORGE)
    moved.roster = _roster("b1")
    moved.rosterDigest = roster_digest(_roster("someone-else"))
    await _add(db_session, held, moved)
    await _add(
        db_session,
        _verdict(held, "a1", "PASS"),
        _verdict(held, "a9", "FAIL"),
        _verdict(moved, "b1", "PASS"),
    )

    async with fresh_session(db_session) as s:
        on_held = await venture_verdict(s, "v-rost", FORGE)
        on_moved = await venture_verdict(s, "v-rost", OTHER_FORGE)
        either = await venture_verdict(s, "v-rost")
    assert (on_held["partition_id"], on_held["verdict"]) == (held.id, "PASS")
    assert (on_moved["partition_id"], on_moved["verdict"]) == (moved.id, "NOT_RUN")
    assert (either["verdict"], either["decided_at"]) == ("NOT_RUN", None)


@pytest.mark.parametrize(
    "payload",
    [
        {"venture_id": "v", "forge_id": ""},
        {"venture_id": "v", "forge_id": 7},
        {"venture_id": "v", "forge_id": "f", "partition_id": "p"},
    ],
)
async def test_a_malformed_v2_body_is_a_422(bridged: AsyncClient, payload: dict) -> None:
    res = await bridged.post(URL, json=payload, headers=AUTH)
    assert res.status_code == 422
