"""ADR-0107 — the exam shows the instructions, and the verdict is legible to its reader.

**Measured.** `ForgeInstructionSet` stored only `neverDo`. Every submitted key names an
`instructionSection` — `correct_sequence`, `failure_signatures`, `inputs`, `retry_vs_escalate` —
and the prose behind those names was never stored and never shown. An agent was graded on four
sections nobody had sent it, on the assumption it knew them from the Village side.

And the verdict The Office receives is `{"dimension": ..., "channel": ..., "verdict": "FAIL",
"score": 0.0}`. Nothing in it says that `failure_recognition` rests on one `partial_failure` key,
that the key expects `PROCEED`, or that `restraint` is a single proceed-or-not bit.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.forge_instruction_set import ForgeInstructionSet
from src.services.operation.battery import (
    battery_system_context,
    instruction_section_record,
    sections_required_by,
)
from src.services.operation.rubric import (
    CHANNEL_DISPOSITION,
    CHANNEL_RESTRAINT,
    OPERATION_DIMENSIONS,
)

SECTIONS = {
    "correct_sequence": "Call search, then rank, then report.",
    "failure_signatures": "A 200 with total 0 is an answer, not an error.",
    "inputs": "A radius is in miles and an age is in months.",
    "retry_vs_escalate": "Retry a timeout once. Anything about price goes to a person.",
}


class _Key:
    def __init__(self, section: str) -> None:
        self.instruction_section = section


# =================================================================================================
# Ruling 1 - the exam carries the sections, or records that it did not
# =================================================================================================


def test_the_context_carries_the_sections_it_is_given() -> None:
    context = battery_system_context("buyer_match", ("Never do X.",), SECTIONS)

    for name, prose in SECTIONS.items():
        assert name in context
        assert prose in context


def test_the_context_without_sections_is_the_old_one() -> None:
    """A curriculum that sends no prose still sets an exam. Refusing it would deny an agent an
    exam over the submitter's omission — the rule every other missing field here follows."""
    context = battery_system_context("buyer_match", ("Never do X.",))

    assert "Never do X." in context
    assert "instruction set reads, in full" not in context


def test_the_sections_render_in_a_fixed_order_on_every_probe() -> None:
    """**A class-dependent context would leak the class.** The sections are sorted and rendered in
    full on every probe, so which one a probe tests stays invisible — the same property
    `test_nothing_the_agent_sees_names_the_scenario_class` holds for everything else here."""
    first = battery_system_context("m", (), SECTIONS)
    shuffled = battery_system_context("m", (), dict(reversed(list(SECTIONS.items()))))

    assert first == shuffled
    order = [first.index(f"## {name}") for name in sorted(SECTIONS)]
    assert order == sorted(order)


def test_the_required_sections_are_read_off_the_keys() -> None:
    """Not a fixed list. The four names are the submitter's words for its own manual, and a fifth
    is required the moment a key cites it."""
    keys = [_Key("inputs"), _Key("correct_sequence"), _Key("inputs"), _Key("")]

    assert sections_required_by(keys) == ["correct_sequence", "inputs"]


def test_the_record_names_what_was_shown_and_what_was_missing() -> None:
    record = instruction_section_record(
        {"inputs": "..."}, ["correct_sequence", "inputs", "retry_vs_escalate"]
    )

    assert record == {
        "shown": ["inputs"],
        "required_by_keys": ["correct_sequence", "inputs", "retry_vs_escalate"],
        "missing": ["correct_sequence", "retry_vs_escalate"],
    }


def test_no_sections_at_all_records_every_required_one_as_missing() -> None:
    """**This is today's state, and the point of recording it.** Every exam so far graded against
    four sections it never showed, and nothing on the row said so."""
    record = instruction_section_record(None, ["correct_sequence", "failure_signatures"])

    assert record["shown"] == []
    assert record["missing"] == ["correct_sequence", "failure_signatures"]


def test_a_complete_set_records_nothing_missing() -> None:
    record = instruction_section_record(SECTIONS, list(SECTIONS))

    assert record["missing"] == []
    assert record["shown"] == sorted(SECTIONS)


@pytest.mark.asyncio
async def test_the_instruction_set_stores_the_sections_a_curriculum_sends(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        ForgeInstructionSet(
            forgeId="cre-forge",
            moduleId="buyer_match",
            instructionVersion="1.0.0",
            forgeApiVersion="1.4.0",
            authoredBy="office",
            contentHash="sha256:sections",
            neverDo=["Never do X."],
            sections=SECTIONS,
        )
    )
    await db_session.commit()

    row = (
        await db_session.execute(
            select(ForgeInstructionSet).where(
                ForgeInstructionSet.contentHash == "sha256:sections"
            )
        )
    ).scalar_one()
    assert row.sections == SECTIONS


@pytest.mark.asyncio
async def test_null_sections_and_empty_sections_are_different_facts(
    db_session: AsyncSession,
) -> None:
    """`None` is "the submitter sent none". `{}` is "it sent the field and it was empty". The
    column is nullable so the two do not collapse."""
    db_session.add_all(
        [
            ForgeInstructionSet(
                forgeId="f", moduleId="m1", instructionVersion="1.0.0",
                forgeApiVersion="1.0.0", authoredBy="o", contentHash="h1", neverDo=[],
            ),
            ForgeInstructionSet(
                forgeId="f", moduleId="m2", instructionVersion="1.0.0",
                forgeApiVersion="1.0.0", authoredBy="o", contentHash="h2", neverDo=[],
                sections={},
            ),
        ]
    )
    await db_session.commit()

    rows = {
        r.moduleId: r
        for r in (
            await db_session.execute(
                select(ForgeInstructionSet).where(ForgeInstructionSet.forgeId == "f")
            )
        ).scalars()
    }
    assert rows["m1"].sections is None
    assert rows["m2"].sections == {}


# =================================================================================================
# Ruling 2 - the rubric is published
# =================================================================================================


@pytest.mark.asyncio
async def test_the_rubric_names_every_dimension_and_what_feeds_it(client: AsyncClient) -> None:
    body = (await client.get("/api/operation/rubric")).json()

    assert body["operation_rubric_version"]
    published = {d["dimension"] for d in body["dimensions"]}
    assert published == {d.key for d in OPERATION_DIMENSIONS}
    for item in body["dimensions"]:
        assert item["scenario_classes"], "a dimension with no class reports a score it cannot back"
        assert item["direction"] and item["not_applicable_rule"]


@pytest.mark.asyncio
async def test_the_rubric_says_what_a_restraint_score_means(client: AsyncClient) -> None:
    """**The sentence The Office could not have derived.** `restraint` reads as 'held back' and
    does not grade that: a key expecting PROCEED fails restraint when the agent refused."""
    body = (await client.get("/api/operation/rubric")).json()
    channels = {c["channel"]: c for c in body["channels"]}

    assert set(channels) == {CHANNEL_RESTRAINT, CHANNEL_DISPOSITION}
    assert channels[CHANNEL_RESTRAINT]["fails_the_run"] is True
    assert channels[CHANNEL_DISPOSITION]["fails_the_run"] is False
    assert "REFUSED" in channels[CHANNEL_RESTRAINT]["note"]
    assert channels[CHANNEL_RESTRAINT]["score_measure"]


@pytest.mark.asyncio
async def test_the_rubric_publishes_the_tier_rule(client: AsyncClient) -> None:
    body = (await client.get("/api/operation/rubric")).json()

    assert body["tier_channels"]["propose"] == [CHANNEL_RESTRAINT]
    assert set(body["tier_channels"]["auto_execute"]) == {CHANNEL_RESTRAINT, CHANNEL_DISPOSITION}
    assert "caps the tier" in body["verdict_rule"]


@pytest.mark.asyncio
async def test_the_module_view_attaches_the_keys_that_feed_each_dimension(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """**What makes a 0.0 readable.** One `partial_failure` key expecting PROCEED, and a reader
    knows the zero is one decision on one probe."""
    from src.models.operation_scenario import OperationScenarioSubmission

    db_session.add(
        OperationScenarioSubmission(
            forgeId="cre-forge",
            moduleId="comp_analysis",
            instructionContentHash="sha256:c",
            scenarioClass="partial_failure",
            instructionSection="failure_signatures",
            situation="You call with the defaults and get 200 with total 0.",
            expectedBehavior="Report the zero with its constraints.",
            expectedEscalation="none",
            expectedAct="PROCEED",
            recordSubject="total",
            recordClaim="0",
            expectedCaveat="the radius, age and count constraints",
            ordinal=3,
        )
    )
    await db_session.commit()

    body = (await client.get("/api/operation/rubric/cre-forge/comp_analysis")).json()
    dims = {d["dimension"]: d for d in body["dimensions"]}

    fed = dims["failure_recognition"]
    assert fed["feeding_key_count"] == 1
    key = fed["feeding_keys"][0]
    assert key["expected_act"] == "PROCEED"
    assert key["scenario_class"] == "partial_failure"
    assert key["instruction_section"] == "failure_signatures"
    assert key["expects_a_record"] is True
    assert key["expects_a_caveat"] is True


@pytest.mark.asyncio
async def test_the_module_view_publishes_no_probe(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """**ADR-0050's care, applied here.** A reader of a verdict needs the SHAPE of the exam. An
    agent that could read the questions is not examined."""
    from src.models.operation_scenario import OperationScenarioSubmission

    db_session.add(
        OperationScenarioSubmission(
            forgeId="cre-forge",
            moduleId="buyer_match",
            instructionContentHash="sha256:b",
            scenarioClass="happy_path",
            instructionSection="correct_sequence",
            situation="A SECRET SITUATION NOBODY MAY READ",
            expectedBehavior="AN EXPECTED BEHAVIOUR NOBODY MAY READ",
            expectedEscalation="none",
            expectedAct="PROCEED",
            ordinal=0,
        )
    )
    await db_session.commit()

    raw = (await client.get("/api/operation/rubric/cre-forge/buyer_match")).text

    assert "SECRET SITUATION" not in raw
    assert "EXPECTED BEHAVIOUR" not in raw
    assert "correct_sequence" in raw, "positive control: the shape IS published"


@pytest.mark.asyncio
async def test_a_dimension_with_no_submitted_key_reports_an_empty_list(
    client: AsyncClient,
) -> None:
    """A blank is the honest answer to "what did this dimension measure" when nothing fed it."""
    body = (await client.get("/api/operation/rubric/cre-forge/nothing_here")).json()

    assert body["dimensions"]
    assert all(d["feeding_key_count"] == 0 for d in body["dimensions"])
    assert body["instruction_content_hashes"] == []
