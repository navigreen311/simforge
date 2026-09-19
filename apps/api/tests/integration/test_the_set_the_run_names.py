"""ADR-0091 — a battery examines a run against the instruction set the RUN NAMES, never the newest.

The writer upserts on `(forgeId, moduleId, contentHash)`. Three readers keyed on the first two, so
a module holding more than one set — which the writer's own key makes ordinary — had three rules
and no agreement between them.

**`capital-forge/statement_ingest` was the live proof**, not a hypothetical: two rows, and a
battery there probed the 2026-08-21 row's never-do list (an unordered scan, first non-empty wins)
while reporting the 2026-09-07 row's version and hash (`createdAt DESC`, first). Two rows in one
exam, and neither answer said which.

These tests are written so that each one FAILS on the old rule rather than merely passing on the
new one: every fixture gives the module a second, newer set, which is the state under which the
two rules diverge.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.forge_instruction_set import ForgeInstructionSet
from src.services.operation.battery import (
    SKIP_NO_INSTRUCTION_SET,
    BatterySkipped,
    battery_for_run,
)
from src.services.operation.never_do import (
    instruction_set_hashes,
    module_never_do_list,
    module_never_do_lists,
)
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION
from tests.integration.test_operation_battery_run import (
    AGENT,
    FORGE,
    MODULE,
    ScriptedProvider,
    _compliant,
    _examiner_pinned,  # noqa: F401  - autouse fixture, imported so the examiner gate passes
    _runtime,
    open_run,
)

pytestmark = pytest.mark.asyncio

OLD_HASH = "sha256:the-set-the-run-was-opened-under"
NEW_HASH = "sha256:a-later-set-nobody-opened-a-run-against"


#: Explicit and a day apart, not two inserts in a row. Left to the column default the two rows
#: landed within the same instant and the ordering the old rule depended on was a coin toss - which
#: is itself the point, and a poor foundation for a test about that rule.
_EARLIER = datetime(2026, 8, 21, 23, 1, tzinfo=UTC)
_LATER = _EARLIER + timedelta(days=17)


def _iset(
    content_hash: str, never_do: list[str], version: str, created: datetime
) -> ForgeInstructionSet:
    return ForgeInstructionSet(
        forgeId=FORGE,
        moduleId=MODULE,
        instructionVersion=version,
        forgeApiVersion="2.1.3",
        authoredBy="the-office",
        contentHash=content_hash,
        neverDo=never_do,
        createdAt=created,
    )


async def _two_sets(session: AsyncSession) -> None:
    """The older set the run names, and a newer one beside it. The shape `statement_ingest` is in
    today, with the same seventeen days between them."""
    session.add(_iset(OLD_HASH, ["never do the thing the run was examined on"], "1.0.0", _EARLIER))
    session.add(_iset(NEW_HASH, ["never do some later thing"], "2.0.0", _LATER))
    await session.commit()


# =================================================================================================
# The ruling
# =================================================================================================


async def test_the_battery_examines_the_set_the_run_names_not_the_newest(
    db_session: AsyncSession,
) -> None:
    """The run names `OLD_HASH`; a newer set exists. The exam must be the run's.

    Asserted through the never-do list, because that is what the battery actually probes — and it
    is the half that came from the *other* row on `statement_ingest`.
    """
    await _two_sets(db_session)
    await open_run(
        db_session,
        run_ref="op-run-names-its-set",
        unit="A",
        forge_id=FORGE,
        instruction_content_hash=OLD_HASH,
        rubric_kind="operation",
        rubric_version=OPERATION_RUBRIC_VERSION,
        module_id=MODULE,
        agent_id=AGENT,
    )
    await db_session.commit()

    named = await module_never_do_list(db_session, FORGE, MODULE, OLD_HASH)
    newest = await module_never_do_list(db_session, FORGE, MODULE, NEW_HASH)

    assert named == ["never do the thing the run was examined on"]
    assert newest == ["never do some later thing"]
    assert named != newest, "the fixture must make the two rules disagree, or it proves nothing"


async def test_a_run_naming_a_hash_no_set_carries_skips_by_name(
    db_session: AsyncSession,
) -> None:
    """**The behaviour change, stated as a test.**

    The module has an instruction set. The run's hash is not it. Under the old rule the newest set
    was substituted silently and the run was examined against a curriculum it never saw; under
    ADR-0091 it is a named skip, the one ADR-0090 built the day before.
    """
    session = db_session
    session.add(_iset(NEW_HASH, ["never do some later thing"], "2.0.0", _LATER))
    await session.commit()
    await open_run(
        session,
        run_ref="op-run-hash-nobody-holds",
        unit="A",
        forge_id=FORGE,
        instruction_content_hash="sha256:a-hash-simforge-never-received",
        rubric_kind="operation",
        rubric_version=OPERATION_RUBRIC_VERSION,
        module_id=MODULE,
        agent_id=AGENT,
    )
    await session.commit()

    result = await battery_for_run(
        session, "op-run-hash-nobody-holds", runtime=_runtime(ScriptedProvider(_compliant))
    )

    assert isinstance(result, BatterySkipped)
    assert result.reason == SKIP_NO_INSTRUCTION_SET


# =================================================================================================
# The bulk form's key is a triple
# =================================================================================================


async def test_two_sets_for_one_module_are_two_entries_not_one(
    db_session: AsyncSession,
) -> None:
    """The pair was not a key. Keyed by the pair, one of these rows was unreachable — and which
    one was decided by a `select` with no `ORDER BY`."""
    await _two_sets(db_session)

    lists = await module_never_do_lists(db_session)

    assert lists[(FORGE, MODULE, OLD_HASH)] == ["never do the thing the run was examined on"]
    assert lists[(FORGE, MODULE, NEW_HASH)] == ["never do some later thing"]


async def test_instruction_set_hashes_reports_both_newest_first(
    db_session: AsyncSession,
) -> None:
    """For the caller that must REPORT the ambiguity rather than resolve it."""
    await _two_sets(db_session)

    assert await instruction_set_hashes(db_session, FORGE, MODULE) == [NEW_HASH, OLD_HASH]
    assert await instruction_set_hashes(db_session, FORGE, "a_module_with_no_sets") == []


# =================================================================================================
# The operator route says which, instead of picking one
# =================================================================================================


async def test_the_inventory_route_refuses_to_answer_for_a_module_with_two_sets(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Two sets, two true answers. The old route returned one of them and said nothing."""
    await _two_sets(db_session)

    res = await client.get(f"/api/operation/held-out/{FORGE}/{MODULE}")

    assert res.status_code == 422
    detail = res.json()["detail"]
    assert detail["error"] == "more_than_one_instruction_set_for_this_module"
    assert set(detail["content_hashes"]) == {OLD_HASH, NEW_HASH}


async def test_the_inventory_route_answers_when_told_which_set(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _two_sets(db_session)

    res = await client.get(
        f"/api/operation/held-out/{FORGE}/{MODULE}", params={"content_hash": OLD_HASH}
    )

    assert res.status_code == 200
    assert res.json()["obligations_declared"] == 1


async def test_the_inventory_route_is_unchanged_for_a_module_with_one_set(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """One set is the ordinary case, and it must not have grown a required parameter."""
    db_session.add(
        _iset(OLD_HASH, ["never do the thing the run was examined on"], "1.0.0", _EARLIER)
    )
    await db_session.commit()

    res = await client.get(f"/api/operation/held-out/{FORGE}/{MODULE}")

    assert res.status_code == 200
    assert res.json()["obligations_declared"] == 1
