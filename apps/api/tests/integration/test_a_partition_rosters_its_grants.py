"""ADR-0162 - a partition is sat by The Office's live grants, recorded at authoring and sealed.

B102, measured 11 October: Burkham x capitalforge rostered seven sitters, not six. Gianna
Horven's grant on `statement_pull` was retired on 5 October, her runs on it still rostered her,
and her FAIL would have failed Gate 9.5 for a venture she no longer operates in.

Every assertion reads back from a fresh session.
"""

from __future__ import annotations

import hashlib
import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.held_out_partition import (
    HeldOutPartition,
    HeldOutPartitionScenario,
    HeldOutPartitionVerdict,
)
from src.models.partition_operator import PartitionOperatorEvent
from src.services.operation import held_out_partition as hp
from src.services.operation import partition_grading
from src.services.operation.partition_roster import (
    REFUSED_ROSTER_ELSEWHERE,
    REFUSED_ROSTER_EMPTY,
    REFUSED_ROSTER_INVALID,
    REFUSED_ROSTER_REPEATS,
    partition_roster,
    record_roster,
    roster_digest,
)
from src.services.operation.partition_verdict import venture_verdict
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION, PARTITION_PROTOCOL_VERSION
from tests.integration import test_partition_authoring as authoring
from tests.integration import test_partition_sweep as sweep
from tests.integration.operators import credential_of, ensure
from tests.integration.scheduler_path import fresh_session, run_scheduled
from tests.integration.test_operation_battery_run import (
    _examiner_pinned,  # noqa: F401 - autouse: pins the examiner for every test here
)
from tests.unit.test_operation_battery import ScriptedProvider, _compliant

pytestmark = pytest.mark.asyncio

#: Ran the partition's module, grant retired: on run history, never on the grants.
RETIRED = "gianna_horven"
STATED_AT = "2026-10-29T15:00:00+00:00"


def _statement(venture: str, forge: str, *grants: tuple[str, str, str], **extra) -> dict:
    return {
        "venture_id": venture,
        "forge_id": forge,
        "stated_at": STATED_AT,
        "grants": [{"grant_id": g, "agent_id": a, "module_id": m} for g, a, m in grants],
        **extra,
    }


async def _partition(db: AsyncSession, pid: str) -> HeldOutPartition:
    async with fresh_session(db) as s:
        return await s.get(HeldOutPartition, pid)


async def _scenario_digests(db: AsyncSession, pid: str) -> list[str]:
    async with fresh_session(db) as s:
        return list(
            (
                await s.execute(
                    select(HeldOutPartitionScenario.digest).where(
                        HeldOutPartitionScenario.partitionId == pid
                    )
                )
            )
            .scalars()
            .all()
        )


# --- authoring records the roster ----------------------------------------------


async def _author_with(db: AsyncSession, roster: dict) -> str:
    async with fresh_session(db) as s:
        await ensure(s, "ivan")
        return await hp.author_partition(
            s,
            authoring.VENTURE,
            authoring.FORGE,
            "ivan",
            credential=credential_of("ivan"),
            roster=roster,
        )


async def test_authoring_records_the_grants_on_the_partitions_modules(
    db_session: AsyncSession,
) -> None:
    await authoring._seed(db_session)
    pid = await _author_with(
        db_session,
        _statement(
            authoring.VENTURE,
            authoring.FORGE,
            ("g-2", "ivy_varos", "record_consent"),
            ("g-1", "ivy_varos", "portfolio_health"),
            # No never-do list, so not in the partition: nothing to sit.
            ("g-3", "ivy_varos", "no_rules"),
        ),
    )

    row = await _partition(db_session, pid)
    assert row.roster == {
        "stated_at": STATED_AT,
        "grants": [
            {"grant_id": "g-1", "agent_id": "ivy_varos", "module_id": "portfolio_health"},
            {"grant_id": "g-2", "agent_id": "ivy_varos", "module_id": "record_consent"},
        ],
    }
    assert row.rosterDigest == roster_digest(row.roster)


@pytest.mark.parametrize(
    ("statement", "code"),
    [
        (
            _statement("another-venture", authoring.FORGE, ("g-1", "a", "record_consent")),
            REFUSED_ROSTER_ELSEWHERE,
        ),
        (
            _statement(
                authoring.VENTURE,
                authoring.FORGE,
                ("g-1", "a", "record_consent"),
                ("g-1", "b", "portfolio_health"),
            ),
            REFUSED_ROSTER_REPEATS,
        ),
        (
            _statement(authoring.VENTURE, authoring.FORGE, ("g-1", "a", "no_rules")),
            REFUSED_ROSTER_EMPTY,
        ),
        (
            _statement(
                authoring.VENTURE, authoring.FORGE, ("g-1", "a", "record_consent"), revoked=[]
            ),
            REFUSED_ROSTER_INVALID,
        ),
    ],
    ids=["another-venture", "repeated-grant", "sits-nobody", "unknown-key"],
)
async def test_a_roster_it_cannot_record_is_refused_and_nothing_is_written(
    db_session: AsyncSession, statement: dict, code: str
) -> None:
    await authoring._seed(db_session)
    with pytest.raises(hp.PartitionRefused, match=code):
        await _author_with(db_session, statement)
    assert await authoring._partitions(db_session) == []


# --- the seal binds it -----------------------------------------------------------


async def test_the_seal_folds_the_roster_into_the_content_digest(
    db_session: AsyncSession,
) -> None:
    await authoring._seed(db_session)
    pid = await _author_with(
        db_session,
        _statement(authoring.VENTURE, authoring.FORGE, ("g-1", "ivy_varos", "record_consent")),
    )
    digest = await authoring._seal(db_session, pid)

    row = await _partition(db_session, pid)
    scenarios = await _scenario_digests(db_session, pid)
    assert digest == row.contentDigest == hp.content_digest(scenarios, row.rosterDigest)
    # The roster moves the digest: the same scenarios sealed with no roster read otherwise.
    assert digest != hp.content_digest(scenarios)


async def test_a_roster_changed_before_the_seal_is_not_sealed(db_session: AsyncSession) -> None:
    await authoring._seed(db_session)
    pid = await _author_with(
        db_session,
        _statement(authoring.VENTURE, authoring.FORGE, ("g-1", "ivy_varos", "record_consent")),
    )
    async with fresh_session(db_session) as s:
        row = await s.get(HeldOutPartition, pid)
        grants = [*row.roster["grants"]]
        grants.append({"grant_id": "g-9", "agent_id": RETIRED, "module_id": "record_consent"})
        row.roster = {**row.roster, "grants": grants}
        await s.commit()

    with pytest.raises(hp.PartitionRefused, match="Author it again"):
        await authoring._seal(db_session, pid)

    row = await _partition(db_session, pid)
    assert (row.status, row.contentDigest) == ("authoring", None)
    async with fresh_session(db_session) as s:
        refusals = (
            (
                await s.execute(
                    select(PartitionOperatorEvent.refusal).where(
                        PartitionOperatorEvent.partitionId == pid,
                        PartitionOperatorEvent.act == "seal",
                    )
                )
            )
            .scalars()
            .all()
        )
    assert refusals == [hp.REFUSED_ROSTER_CHANGED]


# --- older partitions are unchanged --------------------------------------------


async def test_a_partition_authored_without_a_roster_seals_as_it_always_did(
    db_session: AsyncSession,
) -> None:
    await authoring._seed(db_session)
    pid = await authoring._author(db_session)
    digest = await authoring._seal(db_session, pid)

    row = await _partition(db_session, pid)
    assert (row.roster, row.rosterDigest) == (None, None)
    joined = "\n".join(sorted(await _scenario_digests(db_session, pid)))
    assert digest == hashlib.sha256(joined.encode("utf-8")).hexdigest()


async def test_without_a_recorded_roster_run_history_still_rosters(
    db_session: AsyncSession,
) -> None:
    """Control: ADR-0152 is unchanged for a partition with no roster, retired agent and all."""
    await sweep._seed(db_session, agents=((sweep.VENTURE, sweep.AGENT), (sweep.VENTURE, RETIRED)))
    async with fresh_session(db_session) as s:
        roster = await partition_roster(
            s, venture_id=sweep.VENTURE, forge_id=sweep.FORGE, scope={sweep.MODULE}
        )
    assert {a.agent_id for a in roster} == {sweep.AGENT, RETIRED}


# --- a retired agent is not rostered ---------------------------------------------


async def _roster_the_sweeps_partition(db: AsyncSession, pid: str, *agents: str) -> None:
    """Record a roster on a seeded partition and seal it the way `seal_partition` does."""
    statement = _statement(
        sweep.VENTURE,
        sweep.FORGE,
        *((f"grant-{a}", a, sweep.MODULE) for a in agents),
    )
    scenarios = await _scenario_digests(db, pid)
    async with fresh_session(db) as s:
        row = await s.get(HeldOutPartition, pid)
        row.roster = record_roster(
            statement, venture_id=sweep.VENTURE, forge_id=sweep.FORGE, scope={sweep.MODULE}
        )
        row.rosterDigest = roster_digest(row.roster)
        row.contentDigest = hp.content_digest(scenarios, row.rosterDigest)
        await s.commit()


async def _verdict_row(db: AsyncSession, pid: str, agent: str, verdict: str) -> None:
    async with fresh_session(db) as s:
        row = await s.get(HeldOutPartition, pid)
        s.add(
            HeldOutPartitionVerdict(
                partitionId=pid,
                ventureId=sweep.VENTURE,
                agentId=agent,
                verdict=verdict,
                partitionDigest=row.contentDigest,
                protocolVersion=PARTITION_PROTOCOL_VERSION,
                rubricVersion=OPERATION_RUBRIC_VERSION,
            )
        )
        await s.commit()


async def test_a_retired_agent_is_not_rostered_and_does_not_hold_the_gate(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B102's shape: the retired agent has runs on the module and no live grant."""
    pid = await sweep._seed(
        db_session, agents=((sweep.VENTURE, sweep.AGENT), (sweep.VENTURE, RETIRED))
    )
    await _roster_the_sweeps_partition(db_session, pid, sweep.AGENT)

    async with fresh_session(db_session) as s:
        row = await s.get(HeldOutPartition, pid)
        roster = await partition_roster(
            s,
            venture_id=sweep.VENTURE,
            forge_id=sweep.FORGE,
            scope={sweep.MODULE},
            recorded=row.roster,
        )
    assert [(a.agent_id, a.modules) for a in roster] == [(sweep.AGENT, (sweep.MODULE,))]

    sweep._serve(monkeypatch, ScriptedProvider(_compliant))
    await run_scheduled("partition_sweep", db_session)
    assert [r.verdict for r in await sweep._rows(db_session)] == sweep._sitting("PASS")
    assert await sweep._rows(db_session, RETIRED) == []

    # A FAIL under this very seal, for the agent the roster does not name, is not read.
    await _verdict_row(db_session, pid, RETIRED, "FAIL")
    async with fresh_session(db_session) as s:
        assert (await venture_verdict(s, sweep.VENTURE))["verdict"] == "PASS"


async def test_a_rostered_agents_fail_still_holds_the_gate(db_session: AsyncSession) -> None:
    """Control: the roster narrows who sits, not what a sitter's verdict means."""
    pid = await sweep._seed(db_session)
    await _roster_the_sweeps_partition(db_session, pid, sweep.AGENT)
    await _verdict_row(db_session, pid, sweep.AGENT, "FAIL")
    async with fresh_session(db_session) as s:
        assert (await venture_verdict(s, sweep.VENTURE))["verdict"] == "FAIL"


# --- after the seal, the seal still binds ---------------------------------------


async def test_a_roster_edited_after_the_seal_is_not_graded_and_answers_not_run(
    db_session: AsyncSession,
) -> None:
    pid = await sweep._seed(
        db_session, agents=((sweep.VENTURE, sweep.AGENT), (sweep.VENTURE, RETIRED))
    )
    await _roster_the_sweeps_partition(db_session, pid, sweep.AGENT)
    await _verdict_row(db_session, pid, sweep.AGENT, "PASS")
    async with fresh_session(db_session) as s:
        row = await s.get(HeldOutPartition, pid)
        grants = [
            *row.roster["grants"],
            {"grant_id": "grant-x", "agent_id": RETIRED, "module_id": sweep.MODULE},
        ]
        row.roster = {**row.roster, "grants": grants}
        await s.commit()

    async with fresh_session(db_session) as s:
        assert (await venture_verdict(s, sweep.VENTURE))["verdict"] == "NOT_RUN"

    async with fresh_session(db_session) as s:
        # Refused before the runtime is touched.
        outcome = await partition_grading.grade_partition(s, pid, runtime=None)
    assert outcome.skipped == partition_grading.SKIP_SEAL_BROKEN
    assert await sweep._rows(db_session, RETIRED) == []


async def test_a_roster_and_its_digest_edited_together_are_still_not_graded(
    db_session: AsyncSession,
) -> None:
    """The digest beside the roster can be rewritten with it; the seal's digest cannot."""
    pid = await sweep._seed(
        db_session, agents=((sweep.VENTURE, sweep.AGENT), (sweep.VENTURE, RETIRED))
    )
    await _roster_the_sweeps_partition(db_session, pid, sweep.AGENT)
    async with fresh_session(db_session) as s:
        row = await s.get(HeldOutPartition, pid)
        grants = [
            *row.roster["grants"],
            {"grant_id": "grant-x", "agent_id": RETIRED, "module_id": sweep.MODULE},
        ]
        row.roster = {**row.roster, "grants": grants}
        row.rosterDigest = roster_digest(row.roster)
        await s.commit()

    async with fresh_session(db_session) as s:
        # Refused before the runtime is touched.
        outcome = await partition_grading.grade_partition(s, pid, runtime=None)
    assert outcome.skipped == partition_grading.SKIP_SEAL_BROKEN
    assert await sweep._rows(db_session) == []
    assert await sweep._rows(db_session, RETIRED) == []


# --- the operator CLI ------------------------------------------------------------


async def test_the_cli_reads_a_roster_file_and_says_how_many_it_rosters(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from scripts import author_partition as cli
    from tests.integration.scheduler_path import _maker

    await authoring._seed(db_session)
    async with fresh_session(db_session) as s:
        await ensure(s, "ivan")
    monkeypatch.setattr(cli, "SessionLocal", _maker(db_session))
    path = tmp_path / "roster.json"
    path.write_text(
        json.dumps(
            _statement(
                authoring.VENTURE,
                authoring.FORGE,
                ("g-1", "ivy_varos", "record_consent"),
                ("g-2", "ivy_varos", "portfolio_health"),
                ("g-3", "taylor_zhang", "portfolio_health"),
            )
        ),
        encoding="utf-8",
    )

    out = await cli._run(
        cli.argparse.Namespace(
            venture=authoring.VENTURE,
            forge=authoring.FORGE,
            by="ivan",
            modules=None,
            roster=str(path),
            seal_id=None,
            sealed_by=None,
            enrol=None,
        ),
        lambda q: credential_of(q.removeprefix("Credential for ").removesuffix(": ")),
    )
    assert out["rostered_agents"] == 2
    row = await _partition(db_session, out["partition_id"])
    assert len(row.roster["grants"]) == 3


# --- the migration ---------------------------------------------------------------


async def test_the_migration_adds_both_columns_and_backfills_nothing() -> None:
    from pathlib import Path

    sql = (
        Path(__file__).resolve().parents[4]
        / "packages"
        / "db"
        / "migrations"
        / "20261029000000_a_partition_records_its_roster"
        / "migration.sql"
    ).read_text(encoding="utf-8")
    assert '"roster" JSONB' in sql
    assert '"rosterDigest" TEXT' in sql
    assert "UPDATE" not in sql.upper()
