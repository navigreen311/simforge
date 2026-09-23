"""A certification's instruction_sections is readable (ADR-0112).

Recorded on the row since ADR-0107, serialized by nothing. The Office held
NULL on every certification; only SQL against SimForge could read it.

Assert the row, not the response. Each case reads the certification back
from a fresh session, then requires the route to publish exactly that. Two
certifications - one missing a section, one missing none - must come back
different. An endpoint that read nothing could not tell them apart.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.forge_instruction_set import ForgeInstructionSet
from src.models.operation_cert import OperationCertification
from src.models.operation_run import OperationRun
from src.services.operation.battery import instruction_section_record
from tests.integration.scheduler_path import fresh_session

FORGE = "cre-forge"
MODULE = "buyer_match"
HASH = "sha256:sections"
REQUIRED = ["correct_sequence", "failure_signatures", "inputs", "retry_vs_escalate"]
#: Prose The Office sent for one section. It must never come back.
PROSE = (
    "WHEN A BUYER'S STATED BUDGET AND PROOF OF FUNDS DISAGREE, THE AGENT HOLDS "
    "THE MATCH, RECORDS BOTH FIGURES, AND ESCALATES TO THE DEAL LEAD WITH THE "
    "DOCUMENT REFERENCE RATHER THAN CHOOSING ONE OF THE TWO NUMBERS ITSELF."
)


def _run(ref: str, agent: str) -> OperationRun:
    return OperationRun(
        runRef=ref,
        unit="A",
        forgeId=FORGE,
        moduleId=MODULE,
        agentId=agent,
        instructionContentHash=HASH,
        rubricKind="operation",
        rubricVersion="0.2.0",
        startedAt=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5),
        windowMinutes=180,
        scenarioCount=7,
        coverageDenominator=12,
    )


def _cert(agent: str, sections: dict | None) -> OperationCertification:
    return OperationCertification(
        unitType="agent_operation",
        state="provisional",
        forgeId=FORGE,
        moduleId=MODULE,
        agentId=agent,
        instructionVersion="1.0.0",
        forgeApiVersion="3.0.0",
        instructionContentHash=HASH,
        operationRubricVersion="0.2.0",
        instructionSections=sections,
    )


async def _seed(session: AsyncSession) -> None:
    """Three exams, recorded the way the battery records them."""
    gap = instruction_section_record(
        {"correct_sequence": PROSE, "inputs": "x", "retry_vs_escalate": "y"}, REQUIRED
    )
    whole = instruction_section_record({name: PROSE for name in REQUIRED}, REQUIRED)
    session.add_all(
        [
            _run("sec-gap", "a-gap"),
            _cert("a-gap", gap),
            _run("sec-whole", "a-whole"),
            _cert("a-whole", whole),
            _run("sec-none", "a-none"),
            _cert("a-none", None),
        ]
    )
    await session.commit()


async def _row(session: AsyncSession, agent: str) -> dict | None:
    async with fresh_session(session) as s:
        cert = (
            await s.execute(
                select(OperationCertification).where(OperationCertification.agentId == agent)
            )
        ).scalar_one()
        return cert.instructionSections


async def _published(client: AsyncClient, ref: str) -> tuple[dict | None, str]:
    res = await client.get(f"/api/operation/battery-result/{ref}")
    assert res.status_code == 200
    [cert] = res.json()["certifications"]
    return cert["instruction_sections"], res.text


async def test_a_gap_and_no_gap_are_read_off_their_rows_and_differ(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)

    gap_row = await _row(db_session, "a-gap")
    whole_row = await _row(db_session, "a-whole")
    # The rows first. This is what the battery wrote.
    assert gap_row is not None and gap_row["missing"] == ["failure_signatures"]
    assert whole_row is not None and whole_row["missing"] == []

    gap, _ = await _published(client, "sec-gap")
    whole, _ = await _published(client, "sec-whole")

    # Then the route: exactly each row, and so not each other.
    assert gap == gap_row
    assert whole == whole_row
    assert gap != whole


async def test_the_three_fields_stay_distinct(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Not a boolean. `missing` is only readable beside what it is missing from."""
    await _seed(db_session)
    gap, _ = await _published(client, "sec-gap")

    assert set(gap) == {"shown", "required_by_keys", "missing"}
    assert gap["required_by_keys"] == REQUIRED
    assert gap["shown"] == ["correct_sequence", "inputs", "retry_vs_escalate"]
    assert gap["missing"] == ["failure_signatures"]


async def test_nothing_recorded_is_null_not_an_empty_gap(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A pre-ADR-0107 row checked nothing. `missing: []` would claim it had."""
    await _seed(db_session)
    assert await _row(db_session, "a-none") is None

    none, _ = await _published(client, "sec-none")
    whole, _ = await _published(client, "sec-whole")

    assert none is None
    assert none != whole


async def test_names_only_never_the_prose(client: AsyncClient, db_session: AsyncSession) -> None:
    """The prose is on the instruction set. It must not ride along."""
    db_session.add(
        ForgeInstructionSet(
            forgeId=FORGE,
            moduleId=MODULE,
            instructionVersion="1.0.0",
            forgeApiVersion="3.0.0",
            authoredBy="the-office",
            contentHash=HASH,
            neverDo=[],
            sections={name: PROSE for name in REQUIRED},
        )
    )
    await _seed(db_session)

    for ref in ("sec-gap", "sec-whole"):
        _, raw = await _published(client, ref)
        assert "BUYER'S STATED BUDGET" not in raw
        assert "failure_signatures" in raw  # positive control: the names do


async def test_a_key_added_to_the_row_later_is_not_published(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The route projects three fields. A fourth arrives only by review."""
    db_session.add_all(
        [
            _run("sec-extra", "a-extra"),
            _cert(
                "a-extra",
                {"shown": [], "required_by_keys": ["inputs"], "missing": ["inputs"], "text": PROSE},
            ),
        ]
    )
    await db_session.commit()

    published, raw = await _published(client, "sec-extra")
    assert set(published) == {"shown", "required_by_keys", "missing"}
    assert "BUYER'S STATED BUDGET" not in raw


# --- The Office's guard, unchanged ------------------------------------------
#
# Copied from theoffice `broker/simforge.py` at 9015a36: FORBIDDEN_NAME_FRAGMENTS,
# `assert_no_scenario_content` and `_looks_like_prose`. Copied rather than
# imported: the two repos share no code. The field must pass with `echoed=None`
# - no echo exemption - because the ruling says it passes unchanged.

OFFICE_FORBIDDEN_NAME_FRAGMENTS = (
    "scenario_body",
    "scenario_text",
    "scenario_content",
    "scenarios",
    "held_out",
    "heldout",
    "prompt",
    "expected_answer",
    "expected_output",
    "rubric_detail",
    "answer_key",
    "transcript",
    "case_text",
)


def _office_looks_like_prose(value: str) -> bool:
    if len(value) < 200:
        return False
    words = value.split()
    return len(words) >= 30 and value.count(" ") > 20


def _office_assert_no_scenario_content(body: Any, path: str = "") -> None:
    if isinstance(body, dict):
        for key, value in body.items():
            here = f"{path}.{key}" if path else key
            for fragment in OFFICE_FORBIDDEN_NAME_FRAGMENTS:
                assert fragment not in key.lower(), f"{here} matches {fragment!r}"
            _office_assert_no_scenario_content(value, here)
    elif isinstance(body, list):
        for i, item in enumerate(body):
            _office_assert_no_scenario_content(item, f"{path}[{i}]")
    elif isinstance(body, str):
        assert not _office_looks_like_prose(body), f"{path} is prose"


def test_the_copied_guard_still_catches_prose() -> None:
    """Positive control: a guard that passes everything proves nothing."""
    try:
        _office_assert_no_scenario_content({"instruction_sections": {"shown": [PROSE]}})
    except AssertionError:
        return
    raise AssertionError("the copied guard let prose through")


async def test_the_field_passes_the_office_guard_without_exemption(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    for ref in ("sec-gap", "sec-whole", "sec-none"):
        body = (await client.get(f"/api/operation/battery-result/{ref}")).json()
        _office_assert_no_scenario_content(body)
