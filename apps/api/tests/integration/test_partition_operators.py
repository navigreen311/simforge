"""ADR-0154 - author and seal authenticate as the named person; both acts are audited.

Every assertion reads rows back from a fresh session. A refusal must leave its
audit row and nothing else; a success must leave the act and its audit row.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.held_out_partition import HeldOutPartition, HeldOutPartitionSeal
from src.models.partition_operator import PartitionOperator, PartitionOperatorEvent
from src.services.operation import held_out_partition as hp
from src.services.operation import partition_operators as po
from tests.integration.operators import credential_of, ensure
from tests.integration.scheduler_path import fresh_session
from tests.integration.test_partition_authoring import FORGE, VENTURE, _seed

pytestmark = pytest.mark.asyncio

AUTHOR = "Ivan Green"
SEALER = "Grace Hopper"
WRONG = "not anybody's credential at all"


async def _events(db: AsyncSession) -> list[PartitionOperatorEvent]:
    async with fresh_session(db) as s:
        return list(
            (await s.execute(select(PartitionOperatorEvent).order_by(PartitionOperatorEvent.at)))
            .scalars()
            .all()
        )


async def _partitions(db: AsyncSession) -> list[HeldOutPartition]:
    async with fresh_session(db) as s:
        return list((await s.execute(select(HeldOutPartition))).scalars().all())


async def _author(db: AsyncSession, by: str = AUTHOR, credential: str | None = None) -> str:
    async with fresh_session(db) as s:
        return await hp.author_partition(
            s, VENTURE, FORGE, by, credential=credential or credential_of(by)
        )


async def _seal(db: AsyncSession, pid: str, by: str, credential: str | None = None) -> str:
    async with fresh_session(db) as s:
        return await hp.seal_partition(s, pid, by, credential=credential or credential_of(by))


async def _enrolled(db: AsyncSession, *names: str) -> None:
    async with fresh_session(db) as s:
        for name in names:
            await ensure(s, name)


def _no_credential_in(rows: list[PartitionOperatorEvent], *credentials: str) -> None:
    text = json.dumps([{c.key: str(getattr(r, c.key)) for c in r.__table__.columns} for r in rows])
    for credential in credentials:
        assert credential not in text


# --- authoring ------------------------------------------------------------------------------


async def test_the_author_must_know_their_credential(db_session: AsyncSession) -> None:
    await _seed(db_session)
    await _enrolled(db_session, AUTHOR)

    with pytest.raises(hp.PartitionRefused, match="could not be authenticated"):
        await _author(db_session, credential=WRONG)

    assert await _partitions(db_session) == []
    [event] = await _events(db_session)
    assert (event.act, event.outcome, event.refusal) == ("author", "refused", po.REFUSED_WRONG)
    assert event.claimedName == AUTHOR and event.ventureId == VENTURE
    _no_credential_in([event], WRONG, credential_of(AUTHOR))


async def test_a_typed_name_nobody_enrolled_cannot_author(db_session: AsyncSession) -> None:
    await _seed(db_session)
    with pytest.raises(hp.PartitionRefused, match="could not be authenticated"):
        await _author(db_session, by="Someone Typed")

    assert await _partitions(db_session) == []
    [event] = await _events(db_session)
    assert (event.outcome, event.refusal, event.operatorId) == (
        "refused",
        po.REFUSED_UNKNOWN,
        None,
    )


async def test_authoring_records_the_operator_and_audits_it(db_session: AsyncSession) -> None:
    await _seed(db_session)
    await _enrolled(db_session, AUTHOR)

    # Typed loosely; recorded as enrolled.
    pid = await _author(db_session, by="  ivan GREEN ")

    [row] = await _partitions(db_session)
    [event] = await _events(db_session)
    assert row.authoredBy == AUTHOR
    assert row.authoredByOperatorId == event.operatorId is not None
    assert (event.act, event.outcome, event.partitionId) == ("author", "done", pid)


# --- sealing --------------------------------------------------------------------------------


async def test_a_second_operator_seals_and_both_acts_are_audited(db_session: AsyncSession) -> None:
    await _seed(db_session)
    await _enrolled(db_session, AUTHOR, SEALER)
    pid = await _author(db_session)

    await _seal(db_session, pid, SEALER)

    [row] = await _partitions(db_session)
    assert row.status == "sealed" and row.sealedBy == SEALER
    assert row.sealedByOperatorId not in (None, row.authoredByOperatorId)
    events = await _events(db_session)
    assert [(e.act, e.outcome) for e in events] == [("author", "done"), ("seal", "done")]
    assert events[1].operatorId == row.sealedByOperatorId
    _no_credential_in(events, credential_of(AUTHOR), credential_of(SEALER))


async def test_the_sealer_must_know_their_credential(db_session: AsyncSession) -> None:
    await _seed(db_session)
    await _enrolled(db_session, AUTHOR, SEALER)
    pid = await _author(db_session)

    with pytest.raises(hp.PartitionRefused, match="could not be authenticated"):
        await _seal(db_session, pid, SEALER, credential=credential_of(AUTHOR))

    [row] = await _partitions(db_session)
    assert (row.status, row.sealedBy, row.sealedByOperatorId) == ("authoring", None, None)
    async with fresh_session(db_session) as s:
        assert (await s.execute(select(HeldOutPartitionSeal))).first() is None
    seal = [e for e in await _events(db_session) if e.act == "seal"]
    assert [(e.outcome, e.refusal, e.partitionId) for e in seal] == [
        ("refused", po.REFUSED_WRONG, pid)
    ]


async def test_the_author_cannot_seal_under_another_spelling(db_session: AsyncSession) -> None:
    await _seed(db_session)
    await _enrolled(db_session, AUTHOR)
    pid = await _author(db_session)

    with pytest.raises(hp.PartitionRefused, match="never the author"):
        await _seal(db_session, pid, " IVAN green")

    assert (await _partitions(db_session))[0].status == "authoring"
    seal = [e for e in await _events(db_session) if e.act == "seal"]
    assert [(e.outcome, e.refusal) for e in seal] == [("refused", po.REFUSED_SAME_OPERATOR)]


async def test_a_partition_authored_by_typed_name_cannot_be_sealed(
    db_session: AsyncSession,
) -> None:
    """Grandfathering stops at the seal: an authoring partition from before ADR-0154 has no
    authenticated author, so it is authored again rather than sealed."""
    await _seed(db_session)
    await _enrolled(db_session, SEALER)
    async with fresh_session(db_session) as s:
        row = HeldOutPartition(ventureId=VENTURE, forgeId=FORGE, authoredBy=AUTHOR)
        s.add(row)
        await s.commit()
        pid = row.id

    with pytest.raises(hp.PartitionRefused, match="before authentication"):
        await _seal(db_session, pid, SEALER)

    seal = [e for e in await _events(db_session) if e.act == "seal"]
    assert [e.refusal for e in seal] == [hp.REFUSED_AUTHOR_UNAUTHENTICATED]


async def test_the_database_refuses_one_operator_in_both_roles(db_session: AsyncSession) -> None:
    async with fresh_session(db_session) as s:
        s.add(
            HeldOutPartition(
                ventureId=VENTURE,
                forgeId=FORGE,
                status="sealed",
                authoredBy=AUTHOR,
                sealedBy=SEALER,
                contentDigest="sha256:x",
                authoredByOperatorId="op-1",
                sealedByOperatorId="op-1",
            )
        )
        with pytest.raises(IntegrityError):
            await s.commit()


# --- enrolment ------------------------------------------------------------------------------


async def _enrol(db: AsyncSession, name: str, credential: str, **witness: str | None) -> str:
    async with fresh_session(db) as s:
        return await po.enrol_operator(s, name, credential, **witness)


async def test_the_first_operator_needs_no_witness_and_later_ones_do(
    db_session: AsyncSession,
) -> None:
    first = await _enrol(db_session, AUTHOR, credential_of(AUTHOR))

    with pytest.raises(po.OperatorRefused) as refused:
        await _enrol(db_session, SEALER, credential_of(SEALER))
    assert refused.value.code == po.REFUSED_NO_WITNESS

    second = await _enrol(
        db_session,
        SEALER,
        credential_of(SEALER),
        witness_name=AUTHOR,
        witness_credential=credential_of(AUTHOR),
    )

    async with fresh_session(db_session) as s:
        rows = {r.id: r for r in (await s.execute(select(PartitionOperator))).scalars()}
    assert rows[first].witnessedBy is None
    assert rows[second].witnessedBy == first
    events = await _events(db_session)
    assert [(e.act, e.outcome, e.refusal) for e in events] == [
        ("enrol", "done", None),
        ("enrol", "refused", po.REFUSED_NO_WITNESS),
        ("enrol", "done", None),
    ]
    assert events[2].witnessOperatorId == first


@pytest.mark.parametrize(
    ("witness", "credential", "code"),
    [
        (AUTHOR, WRONG, po.REFUSED_WITNESS_FAILED),
        ("Nobody Enrolled", WRONG, po.REFUSED_WITNESS_FAILED),
        (" grace HOPPER", credential_of(SEALER), po.REFUSED_SELF_WITNESS),
    ],
)
async def test_a_witness_must_authenticate_and_be_someone_else(
    db_session: AsyncSession, witness: str, credential: str, code: str
) -> None:
    await _enrol(db_session, AUTHOR, credential_of(AUTHOR))
    with pytest.raises(po.OperatorRefused) as refused:
        await _enrol(
            db_session,
            SEALER,
            credential_of(SEALER),
            witness_name=witness,
            witness_credential=credential,
        )
    assert refused.value.code == code
    assert await po.find_operator(db_session, SEALER) is None


@pytest.mark.parametrize(
    ("name", "credential", "code"),
    [
        ("Ada Lovelace", "x7q", po.REFUSED_WEAK),
        ("system", "long enough credential", po.REFUSED_NOT_A_PERSON),
        ("the office", "long enough credential", po.REFUSED_NOT_A_PERSON),
    ],
)
async def test_enrolment_refuses_a_weak_credential_or_a_non_person(
    db_session: AsyncSession, name: str, credential: str, code: str
) -> None:
    with pytest.raises(po.OperatorRefused) as refused:
        await _enrol(db_session, name, credential)
    assert refused.value.code == code
    [event] = await _events(db_session)
    assert (event.outcome, event.refusal) == ("refused", code)
    _no_credential_in([event], credential)


async def test_a_person_is_enrolled_once(db_session: AsyncSession) -> None:
    await _enrol(db_session, AUTHOR, credential_of(AUTHOR))
    with pytest.raises(po.OperatorRefused) as refused:
        await _enrol(
            db_session,
            "ivan green",
            "another long credential",
            witness_name=AUTHOR,
            witness_credential=credential_of(AUTHOR),
        )
    assert refused.value.code == po.REFUSED_ALREADY


async def test_the_credential_is_stored_only_as_a_salted_hash(db_session: AsyncSession) -> None:
    await _enrol(db_session, AUTHOR, credential_of(AUTHOR))
    async with fresh_session(db_session) as s:
        [row] = (await s.execute(select(PartitionOperator))).scalars().all()
    assert row.credentialHash.startswith("scrypt$")
    assert credential_of(AUTHOR) not in row.credentialHash
    assert po.credential_matches(credential_of(AUTHOR), row.credentialHash)
    assert not po.credential_matches(WRONG, row.credentialHash)
    # Salted: the same credential hashes differently twice.
    assert po.hash_credential("same input value") != po.hash_credential("same input value")


# --- the CLI --------------------------------------------------------------------------------


async def test_the_cli_takes_no_credential_on_the_command_line() -> None:
    from scripts import author_partition as cli

    for flag in ("--credential", "--password", "--secret"):
        with pytest.raises(SystemExit):
            cli.main(["--venture", "v", "--forge", "f", "--by", AUTHOR, flag, "x"], prompt=_never)


def _never(question: str) -> str:
    raise AssertionError(f"prompted before parsing: {question}")


async def test_the_cli_enrols_at_hidden_prompts_and_refuses_a_mistyped_repeat(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    from scripts import author_partition as cli
    from tests.integration.scheduler_path import _maker

    monkeypatch.setattr(cli, "SessionLocal", _maker(db_session))
    answers = iter([credential_of(AUTHOR), "a different repeat entry"])
    assert await_main(cli, ["--enrol", AUTHOR], lambda q: next(answers)) == 2
    assert await po.find_operator(db_session, AUTHOR) is None

    answers = iter([credential_of(AUTHOR), credential_of(AUTHOR)])
    assert await_main(cli, ["--enrol", AUTHOR], lambda q: next(answers)) == 0
    out = capsys.readouterr()
    assert credential_of(AUTHOR) not in out.out + out.err
    assert await po.find_operator(db_session, AUTHOR) is not None


def await_main(cli, argv: list[str], prompt) -> int:  # noqa: ANN001
    """`main` runs its own event loop; run it off this test's loop."""
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        return pool.submit(cli.main, argv, prompt).result()
