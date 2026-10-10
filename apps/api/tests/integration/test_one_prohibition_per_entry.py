"""One prohibition per never-do entry, and a partition scoped to the venture's modules (ADR-0129).

1. The Office stores CapitalForge's never-do lists as one markdown string and wraps it into a
   one-item list. record_consent's eleven prohibitions arrived as ONE entry: one obligation, one
   decline probe asking for several rules at once, and no over-read probe for the claims inside.
   A hand-over carrying such an entry is refused, by name. SimForge does not split it.
2. A partition may be scoped to named modules. Only those are authored and recorded.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.forge_instruction_set import ForgeInstructionSet
from src.models.held_out_partition import HeldOutPartition, HeldOutPartitionScenario
from src.services.operation import held_out_partition as hp
from src.services.operation.scenarios import (
    VIOLATION_SEVERAL_PROHIBITIONS,
    prohibitions_in,
    validate_curriculum_submission,
)
from tests.integration.operators import credential_of, ensure
from tests.integration.scheduler_path import fresh_session
from tests.integration.test_held_out_isolation import _body
from tests.unit.test_held_out_authoring import PORTFOLIO_HEALTH_NEVER_DO

pytestmark = pytest.mark.asyncio

#: The shape that arrived: several bold-led prohibitions in one string.
BLOB = (
    "**Never obtain consent.** Only record consent a human obtained.\n\n"
    "**Never record without an `evidenceRef`** identifying a retrievable artifact.\n\n"
    "**Never backdate.** The timestamp is when the record was made."
)

#: Live cre-forge entries: one prohibition each, with sentences after it.
ONE_EACH = (
    "Never retry after a timeout. The write may have landed and nothing de-duplicates it. "
    "Report the uncertainty and let a human check the deal.",
    "Never call this to 'check' whether a contract can be made. It writes.",
    "Never report `arv` without `arv_confidence`. They are one fact in two fields.",
    "**Never obtain consent.** Only record consent a human obtained.",
)


# --- counting ----------------------------------------------------------------------------


def test_the_blob_holds_three() -> None:
    assert prohibitions_in(BLOB) == 3


def test_live_single_entries_hold_one() -> None:
    assert [prohibitions_in(e) for e in ONE_EACH] == [1, 1, 1, 1]


def test_two_sentences_two_prohibitions() -> None:
    assert prohibitions_in("Never retry. Never widen the radius.") == 2


def test_a_numbered_list_is_counted() -> None:
    assert prohibitions_in("1. Never retry.\n2. Never widen.") == 2


def test_never_inside_a_sentence_does_not_start_one() -> None:
    assert prohibitions_in("Report it and never guess the value.") == 0


# --- ruling 1: the hand-over refuses -----------------------------------------------------


def test_the_validator_names_the_entry_and_the_reason() -> None:
    result = validate_curriculum_submission([], module_never_do={"record_consent": [BLOB]})
    hits = [v for v in result.violations if VIOLATION_SEVERAL_PROHIBITIONS in v]
    assert hits == [
        f"module_never_do[record_consent][0]: {VIOLATION_SEVERAL_PROHIBITIONS} (3 found). "
        "Send one prohibition per entry; SimForge does not split."
    ]


def test_the_validator_accepts_one_per_entry() -> None:
    result = validate_curriculum_submission([], module_never_do={"m": list(ONE_EACH)})
    assert not [v for v in result.violations if VIOLATION_SEVERAL_PROHIBITIONS in v]


async def test_a_blob_hand_over_is_refused_and_nothing_is_written(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    res = await client.post("/api/operation/curriculum", json=_body([BLOB]))
    assert res.status_code == 422, res.text
    assert VIOLATION_SEVERAL_PROHIBITIONS in str(res.json())
    async with fresh_session(db_session) as s:
        assert await s.scalar(select(func.count()).select_from(ForgeInstructionSet)) == 0


async def test_the_same_rules_one_per_entry_are_accepted(client: AsyncClient) -> None:
    res = await client.post(
        "/api/operation/curriculum", json=_body(list(PORTFOLIO_HEALTH_NEVER_DO))
    )
    assert res.status_code == 200, res.text


# --- ruling 2: a partition scoped to the venture's modules -------------------------------


async def _two_modules(db: AsyncSession) -> None:
    for module_id, h in (("in_scope", "h-in"), ("out_of_scope", "h-out")):
        db.add(
            ForgeInstructionSet(
                forgeId="f-s",
                moduleId=module_id,
                instructionVersion="1",
                forgeApiVersion="1",
                authoredBy="o",
                contentHash=h,
                neverDo=list(PORTFOLIO_HEALTH_NEVER_DO),
            )
        )
    await db.commit()


async def test_a_scoped_partition_authors_and_records_only_its_modules(
    db_session: AsyncSession,
) -> None:
    await _two_modules(db_session)
    async with fresh_session(db_session) as s:
        await ensure(s, "Ivan Green")
        pid = await hp.author_partition(
            s,
            "v-s",
            "f-s",
            "Ivan Green",
            modules=["in_scope"],
            credential=credential_of("Ivan Green"),
        )
    async with fresh_session(db_session) as s:
        part = await s.get(HeldOutPartition, pid)
        modules = set(
            (
                await s.execute(
                    select(HeldOutPartitionScenario.moduleId).where(
                        HeldOutPartitionScenario.partitionId == pid
                    )
                )
            ).scalars()
        )
    assert part.instructionHashes == {"in_scope": "h-in"}
    assert modules == {"in_scope"}


async def test_an_unsubmitted_module_in_scope_is_refused_and_nothing_written(
    db_session: AsyncSession,
) -> None:
    await _two_modules(db_session)
    async with fresh_session(db_session) as s:
        await ensure(s, "Ivan Green")
        with pytest.raises(hp.PartitionRefused, match="not_submitted"):
            await hp.author_partition(
                s,
                "v-s",
                "f-s",
                "Ivan Green",
                modules=["in_scope", "not_submitted"],
                credential=credential_of("Ivan Green"),
            )
    async with fresh_session(db_session) as s:
        assert await s.scalar(select(func.count()).select_from(HeldOutPartition)) == 0


async def test_no_scope_is_the_whole_forge(db_session: AsyncSession) -> None:
    await _two_modules(db_session)
    async with fresh_session(db_session) as s:
        await ensure(s, "Ivan Green")
        pid = await hp.author_partition(
            s, "v-s", "f-s", "Ivan Green", credential=credential_of("Ivan Green")
        )
    async with fresh_session(db_session) as s:
        part = await s.get(HeldOutPartition, pid)
    assert set(part.instructionHashes) == {"in_scope", "out_of_scope"}


# --- ADR-0133: a "never" joined into the same sentence ------------------------------------


def test_comma_and_never_is_a_second_prohibition() -> None:
    assert prohibitions_in("Never retry, and never assemble a second export.") == 2


def test_semicolon_never_is_a_second_prohibition() -> None:
    assert prohibitions_in("Never retry; never assemble a second export.") == 2
    assert prohibitions_in("Never retry; and never widen.") == 2


def test_em_dash_never_is_a_second_prohibition() -> None:
    assert prohibitions_in("Never supply another advisorId — and never substitute your own.") == 2
    assert prohibitions_in("Never supply another advisorId —never substitute your own.") == 2


def test_emphasis_before_the_join_still_counts() -> None:
    entry = "**Never report a verdict without its `reasons`**, and never guess."
    assert prohibitions_in(entry) == 2


def test_a_never_inside_a_clause_is_still_not_counted() -> None:
    """Only a join makes a second prohibition. "and will never" is a statement, not a rule."""
    assert prohibitions_in("Never retry. A duplicate will never be caught.") == 1
    assert prohibitions_in("Never retry, because nothing will never de-duplicate it.") == 1


def test_the_validator_refuses_a_joined_entry() -> None:
    result = validate_curriculum_submission(
        [], module_never_do={"m": ["Never retry, and never assemble a second export."]}
    )
    assert any(
        VIOLATION_SEVERAL_PROHIBITIONS in v and "(2 found)" in v for v in result.violations
    )
