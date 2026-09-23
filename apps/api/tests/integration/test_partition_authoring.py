"""ADR-0109 - author and seal write the rows they claim to write.

Every assertion reads back from a fresh session. The work itself runs
in a session of its own that is CLOSED before the read: a function that
only flushed is rolled back on close, and the read finds nothing. The
first test is that negative control, so the harness is shown to bite.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.forge_instruction_set import ForgeInstructionSet
from src.models.held_out_partition import HeldOutPartition, HeldOutPartitionScenario
from src.services.operation import held_out_partition as hp
from src.services.operation.held_out import author_for_modules
from src.services.operation.scenarios import HELD_OUT_CLASSES
from src.utils.time import utcnow
from tests.integration.scheduler_path import fresh_session

pytestmark = pytest.mark.asyncio

FORGE = "capital-forge"
VENTURE = "venture-capital"

OLD_NEVER_DO = ["Never email the client."]
NEVER_DO = {
    "record_consent": ["Never backdate.", "Never retry a timeout."],
    "portfolio_health": ["Never report `score: null` as zero, or as grade F."],
}


async def _seed(session: AsyncSession) -> None:
    earlier = utcnow() - timedelta(days=3)
    rows = [
        # an older set for record_consent: must NOT be the scope (R3)
        ForgeInstructionSet(
            forgeId=FORGE, moduleId="record_consent", instructionVersion="1.0.0",
            forgeApiVersion="1.0.0", authoredBy="office", contentHash="h-old",
            neverDo=OLD_NEVER_DO, createdAt=earlier,
        ),
        ForgeInstructionSet(
            forgeId=FORGE, moduleId="record_consent", instructionVersion="1.1.0",
            forgeApiVersion="1.0.0", authoredBy="office", contentHash="h-rc",
            neverDo=NEVER_DO["record_consent"],
        ),
        ForgeInstructionSet(
            forgeId=FORGE, moduleId="portfolio_health", instructionVersion="1.0.0",
            forgeApiVersion="1.0.0", authoredBy="office", contentHash="h-ph",
            neverDo=NEVER_DO["portfolio_health"],
        ),
        ForgeInstructionSet(
            forgeId=FORGE, moduleId="no_rules", instructionVersion="1.0.0",
            forgeApiVersion="1.0.0", authoredBy="office", contentHash="h-nr",
            neverDo=[],
        ),
        # another forge's list must not leak in
        ForgeInstructionSet(
            forgeId="other-forge", moduleId="elsewhere", instructionVersion="1.0.0",
            forgeApiVersion="1.0.0", authoredBy="office", contentHash="h-x",
            neverDo=["Never delete a ledger."],
        ),
    ]
    session.add_all(rows)
    await session.commit()


async def _author(db: AsyncSession, venture: str = VENTURE, by: str = "ivan") -> str:
    async with fresh_session(db) as s:
        return await hp.author_partition(s, venture, FORGE, by)


#: ADR-0113. Not the author, who is "ivan" throughout.
SEALER = "Grace Hopper"


async def _seal(db: AsyncSession, pid: str, by: str = SEALER) -> str:
    async with fresh_session(db) as s:
        return await hp.seal_partition(s, pid, by)


async def _partitions(db: AsyncSession) -> list[HeldOutPartition]:
    async with fresh_session(db) as s:
        return list((await s.execute(select(HeldOutPartition))).scalars().all())


async def _scenarios(db: AsyncSession, pid: str) -> list[HeldOutPartitionScenario]:
    async with fresh_session(db) as s:
        q = select(HeldOutPartitionScenario).where(
            HeldOutPartitionScenario.partitionId == pid
        )
        return list((await s.execute(q)).scalars().all())


# --- the harness bites ---------------------------------------------------------


async def test_negative_control_a_flush_without_commit_reads_back_empty(
    db_session: AsyncSession,
) -> None:
    async with fresh_session(db_session) as s:
        s.add(HeldOutPartition(ventureId="v", forgeId="f", authoredBy="x"))
        await s.flush()
    assert await _partitions(db_session) == []


# --- author --------------------------------------------------------------------


async def test_author_writes_an_authoring_partition_and_its_scenarios(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)
    pid = await _author(db_session)

    [row] = await _partitions(db_session)
    assert row.id == pid
    assert (row.ventureId, row.forgeId) == (VENTURE, FORGE)
    assert row.status == "authoring"
    assert row.authoredBy == "ivan"
    assert row.contentDigest is None and row.sealedAt is None

    stored = await _scenarios(db_session, pid)
    battery = [s for ss in author_for_modules(NEVER_DO).values() for s in ss]
    assert len(stored) == len(battery) * len(hp.FRAMINGS)
    assert {r.scenarioClass for r in stored} <= HELD_OUT_CLASSES
    assert {r.scenarioClass for r in stored} == HELD_OUT_CLASSES
    assert {r.moduleId for r in stored} == set(NEVER_DO)


async def test_the_scope_is_the_forges_current_sets_only(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)
    pid = await _author(db_session)
    texts = {r.body["obligation_text"] for r in await _scenarios(db_session, pid)}

    assert texts == {t for ts in NEVER_DO.values() for t in ts}
    assert OLD_NEVER_DO[0] not in texts
    assert "Never delete a ledger." not in texts


async def test_each_stored_body_rebuilds_its_scenario_and_matches_its_digest(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)
    pid = await _author(db_session)
    stored = await _scenarios(db_session, pid)
    battery = hp.battery_digests(NEVER_DO)

    for r in stored:
        scenario = hp.scenario_from_body(r.body)
        assert r.digest == hp.body_digest(r.body)
        assert r.digest == hp.scenario_digest(scenario)
        assert r.scenarioClass == scenario.scenario_class
        assert r.moduleId == scenario.module_id
    assert not {r.digest for r in stored} & battery, "R2: disjoint by digest"


async def test_the_seed_is_the_partition_id_and_reproduces_the_rows(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)
    pid = await _author(db_session)
    stored = {r.digest for r in await _scenarios(db_session, pid)}
    again = {hp.scenario_digest(v) for v in hp.adversarial_variants(NEVER_DO, pid)}
    assert stored == again


@pytest.mark.parametrize("by", ["office", "The Office", "the-office"])
async def test_the_office_never_authors_and_nothing_is_written(
    db_session: AsyncSession, by: str
) -> None:
    await _seed(db_session)
    with pytest.raises(hp.PartitionRefused, match="R1"):
        await _author(db_session, by=by)
    assert await _partitions(db_session) == []


async def test_a_forge_with_no_never_do_is_refused_and_nothing_written(
    db_session: AsyncSession,
) -> None:
    async with fresh_session(db_session) as s:
        with pytest.raises(hp.PartitionRefused, match="nothing to hold out"):
            await hp.author_partition(s, VENTURE, "empty-forge", "ivan")
    assert await _partitions(db_session) == []


async def test_an_overlap_with_the_battery_refuses_and_writes_nothing(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)

    def leaky(never_do, seed):  # the battery's own probes, relabelled
        return tuple(s for ss in author_for_modules(never_do).values() for s in ss)

    monkeypatch.setattr(hp, "adversarial_variants", leaky)
    with pytest.raises(hp.PartitionRefused, match="R2"):
        await _author(db_session)
    assert await _partitions(db_session) == []


# --- seal ----------------------------------------------------------------------


async def test_seal_sets_digest_status_and_time(db_session: AsyncSession) -> None:
    await _seed(db_session)
    pid = await _author(db_session)
    returned = await _seal(db_session, pid)

    [row] = await _partitions(db_session)
    digests = [r.digest for r in await _scenarios(db_session, pid)]
    assert row.status == "sealed"
    assert row.sealedAt is not None
    assert row.contentDigest == hp.content_digest(digests) == returned


async def test_sealing_retires_the_earlier_sealed_one_for_that_venture_only(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)
    first = await _author(db_session)
    await _seal(db_session, first)
    other = await _author(db_session, venture="another-venture")
    await _seal(db_session, other)
    second = await _author(db_session)
    await _seal(db_session, second)

    status = {p.id: p.status for p in await _partitions(db_session)}
    assert status == {first: "retired", other: "sealed", second: "sealed"}


async def test_an_empty_partition_cannot_be_sealed(db_session: AsyncSession) -> None:
    async with fresh_session(db_session) as s:
        row = HeldOutPartition(ventureId=VENTURE, forgeId=FORGE, authoredBy="ivan")
        s.add(row)
        await s.commit()
        pid = row.id
    with pytest.raises(hp.PartitionRefused, match="no scenarios"):
        await _seal(db_session, pid)
    [row] = await _partitions(db_session)
    assert row.status == "authoring" and row.contentDigest is None


async def test_a_sealed_partition_cannot_be_sealed_again(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)
    pid = await _author(db_session)
    await _seal(db_session, pid)
    with pytest.raises(hp.PartitionRefused, match="only an authoring"):
        await _seal(db_session, pid)


async def test_sealing_an_unknown_partition_is_refused(db_session: AsyncSession) -> None:
    with pytest.raises(hp.PartitionRefused, match="no partition"):
        await _seal(db_session, "nope")


# --- the operator CLI ----------------------------------------------------------


async def test_the_cli_authors_then_a_second_person_seals_and_no_content_prints(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two invocations, two people (ADR-0113)."""
    import json

    from scripts import author_partition as cli
    from tests.integration.scheduler_path import _maker

    await _seed(db_session)
    monkeypatch.setattr(cli, "SessionLocal", _maker(db_session))
    authored = await cli._run(
        cli.argparse.Namespace(
            venture=VENTURE, forge=FORGE, by="ivan", seal_id=None, sealed_by=None
        )
    )
    sealed = await cli._run(
        cli.argparse.Namespace(
            venture=None, forge=None, by=None,
            seal_id=authored["partition_id"], sealed_by=SEALER,
        )
    )
    printed = json.dumps([authored, sealed])

    [row] = await _partitions(db_session)
    assert authored["status"] == "authoring"
    assert sealed == {
        "partition_id": row.id,
        "scenarios": len(await _scenarios(db_session, row.id)),
        "content_digest": row.contentDigest,
        "status": "sealed",
    }
    assert (row.status, row.authoredBy, row.sealedBy) == ("sealed", "ivan", SEALER)
    assert "backdate" not in printed and "probe" not in printed


async def test_the_cli_cannot_seal_without_naming_the_sealer(capsys) -> None:
    from scripts import author_partition as cli

    with pytest.raises(SystemExit):
        cli.main(["--seal-id", "p-1"])
    assert "--sealed-by" in capsys.readouterr().err
