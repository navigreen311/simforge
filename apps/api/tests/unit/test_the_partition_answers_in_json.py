"""ADR-0140: the partition answers in JSON; the battery and The Office's keys stay text."""

from __future__ import annotations

import hashlib
import json

import pytest

from src.services.operation.battery import (
    ANSWER_SCHEMA,
    JSON_EXAMPLE_CLAIM,
    JSON_EXAMPLE_DECLINE_WITH_A_RECORD,
    JSON_EXAMPLE_ESCALATE,
    JSON_EXAMPLE_NONE,
    JSON_EXAMPLE_REFUSE,
    PARTITION_PROTOCOL,
    RESPONSE_PROTOCOL,
    AgentAnswer,
    ProtocolViolation,
    battery_system_context,
    parse_answer,
    run_module_battery,
)
from src.services.operation.held_out_scoring import (
    REASON_PROTOCOL_UNKNOWN_ACT,
    REASON_PROTOCOL_UNREADABLE_JSON,
    REASON_PROTOCOL_UNREADABLE_RECORD,
)
from src.services.operation.rubric import (
    PARTITION_PROTOCOL_VERSION,
    RESPONSE_PROTOCOL_VERSION,
)
from tests.unit.test_held_out_authoring import PORTFOLIO_HEALTH_NEVER_DO
from tests.unit.test_operation_battery import _compliant, _runtime

#: ADR-0103 for the partition's block: what the agent reads is pinned to its version.
PINNED = {
    "12.0.0": "b6742e73c9a61bbfc71701e32de1550a905f90ed1beef3379679f409e999cc67",
}


def test_the_versions_split() -> None:
    assert RESPONSE_PROTOCOL_VERSION == "11.0.0"
    assert PARTITION_PROTOCOL_VERSION == "12.0.0"


def test_the_json_block_is_pinned_to_its_version() -> None:
    assert PARTITION_PROTOCOL_VERSION in PINNED, "a new version needs its text pinned here"
    digest = hashlib.sha256(PARTITION_PROTOCOL.encode()).hexdigest()
    assert digest == PINNED[PARTITION_PROTOCOL_VERSION], (
        "PARTITION_PROTOCOL changed without a version bump (ADR-0103, ADR-0140)"
    )


def test_the_ordered_test_is_the_text_blocks_word_for_word() -> None:
    """Step 2 is unchanged (the reworded step 2 was measured and dropped)."""
    step2 = "could a person with the right authority or permission make it succeed?"
    assert step2 in RESPONSE_PROTOCOL and step2 in PARTITION_PROTOCOL


def test_the_blocks_differ_only_by_path() -> None:
    battery = battery_system_context("m", PORTFOLIO_HEALTH_NEVER_DO)
    partition = battery_system_context("m", PORTFOLIO_HEALTH_NEVER_DO, protocol=PARTITION_PROTOCOL)
    assert battery.endswith(RESPONSE_PROTOCOL) and "JSON" not in battery
    assert partition.endswith(PARTITION_PROTOCOL)


@pytest.mark.parametrize(
    "example",
    [
        JSON_EXAMPLE_NONE,
        JSON_EXAMPLE_DECLINE_WITH_A_RECORD,
        JSON_EXAMPLE_CLAIM,
        JSON_EXAMPLE_REFUSE,
        JSON_EXAMPLE_ESCALATE,
    ],
)
def test_every_json_example_is_valid_and_readable(example: str) -> None:
    d = json.loads(example)
    assert set(d) == set(ANSWER_SCHEMA["required"])
    assert isinstance(parse_answer(example), AgentAnswer)


def test_a_valid_json_answer_is_read_field_by_field() -> None:
    got = parse_answer(JSON_EXAMPLE_REFUSE)
    assert isinstance(got, AgentAnswer)
    assert (got.act, got.cited_rule, got.record) == ("REFUSE", 9, None)
    got = parse_answer(JSON_EXAMPLE_ESCALATE)
    assert isinstance(got, AgentAnswer)
    assert got.record == ("door_code", "NOT KNOWN") and got.cited_rule is None


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ('{"act": "REFUSE"', REASON_PROTOCOL_UNREADABLE_JSON),
        (
            '{"act": "MAYBE", "cited_rule": null, "record": null, "caveats": []}',
            REASON_PROTOCOL_UNKNOWN_ACT,
        ),
        (
            '{"act": "REFUSE", "cited_rule": null, "record": null, "caveats": []}',
            REASON_PROTOCOL_UNKNOWN_ACT,
        ),
        (
            '{"act": "REFUSE", "cited_rule": true, "record": null, "caveats": []}',
            REASON_PROTOCOL_UNKNOWN_ACT,
        ),
        (
            '{"act": "DECLINE", "cited_rule": null, "record": {"subject": "x"}, "caveats": []}',
            REASON_PROTOCOL_UNREADABLE_RECORD,
        ),
        (
            '{"act": "DECLINE", "cited_rule": null, "record": null, "caveats": "none"}',
            REASON_PROTOCOL_UNREADABLE_JSON,
        ),
    ],
)
def test_an_invalid_json_answer_names_the_rule_it_broke(text: str, reason: str) -> None:
    got = parse_answer(text)
    assert isinstance(got, ProtocolViolation) and got.reason == reason


def test_text_answers_still_read_by_the_line_grammar() -> None:
    got = parse_answer("ACT: DECLINE\nRECORD: NONE")
    assert isinstance(got, AgentAnswer) and got.act == "DECLINE"


async def test_the_battery_sends_the_text_block_and_no_schema() -> None:
    runtime, provider = _runtime(_compliant)
    await run_module_battery(
        module_id="portfolio_health",
        agent_id="agent-under-test",
        never_do=PORTFOLIO_HEALTH_NEVER_DO,
        runtime=runtime,
    )
    assert provider.systems and provider.schemas
    assert all(s is None for s in provider.schemas)
    assert all(sys.endswith(RESPONSE_PROTOCOL) for sys in provider.systems)
