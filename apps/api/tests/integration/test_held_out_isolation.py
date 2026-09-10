"""P-05 — the isolation claim measured on the RECEIVING side, and the round trip that moves a level.

The unit tests prove the authoring module is not REACHABLE from the submitter's request path, by
walking the import graph. That is a claim about code. This file makes the claim about the wire: a
real submission goes through the real endpoint, and the real response body is searched for the probe
text and the grading keys the pipeline produced for that module.

**Why both.** A reachability test would keep passing if somebody serialised a held-out scenario into
a response through a data path the import walk does not describe - a cache, a shared dict, a field
copied by name. A response-body test would keep passing if the endpoint simply had not been asked
the right question yet. Neither is sufficient and the pair is what the card asked for: asserted by a
test, not claimed in a comment.

**What neither proves**, and `GATE_9_5_FLAG` says it in the code: that the party reading the
instruction set to author the held-out set is isolated from the party that could leak it. That is a
process control. This package does not close it and must not read as though it had.
"""

from __future__ import annotations

import json

from httpx import AsyncClient

from src.services.operation.held_out import author_for_module, authored_classes, held_out_fields
from src.services.operation.scenarios import (
    ALL_SCENARIO_CLASSES,
    HELD_OUT_CLASSES,
    LEVEL_CERTIFIED_WITH_DECLARED_ABSENCE,
    LEVEL_DEMONSTRATED,
    classify_certification_level,
)
from tests.unit.test_held_out_authoring import PORTFOLIO_HEALTH_NEVER_DO

MODULE = "portfolio_health"
FORGE = "capitalforge"

#: What The Office actually submits for this module: two supplied classes, five declared absent with
#: a reason. `scenarios/portfolio_health.yaml` on The Office's side is where the split comes from.
SUPPLIED: tuple[str, ...] = ("happy_path", "permission_denied")
DECLARED: dict[str, str] = {
    "escalation_required": (
        "It takes no identifier, writes nothing, and its retry-vs-escalate section reads 'Retry "
        "freely.' in full. There is no failure to hand a human, so there is no escalation to test."
    ),
    "malformed_input": (
        "The module has no caller-supplied value. A malformed-input scenario needs a value the "
        "module can reject and this one takes none."
    ),
    "partial_failure": (
        "One call returns one answer computed over seven tables and returning none of them. There "
        "is no shape in the response that can half-arrive."
    ),
    "rate_limited": (
        "The response table has three rows and none of them is a 429. Nothing in the instruction "
        "describes a quota, a throttle, a backoff or a retry-after."
    ),
    "recovery_after_failure": (
        "It is a pure read and the retry section says retry freely. The recovery is the retry the "
        "instruction already permits, so the scenario would test nothing of its own."
    ),
}


def _body(never_do: list[str]) -> dict:
    return {
        "instruction_set_ref": {
            "forge_id": FORGE,
            "module_id": MODULE,
            "instruction_version": "1.0.0",
            "forge_api_version": "1.0.0",
            "content_hash": "sha256:" + "h" * 8,
        },
        "certification_units_requested": [
            {
                "unit_type": "agent_operation",
                "forge_id": FORGE,
                "agent_id": "taylor_zhang",
                "module_id": MODULE,
            }
        ],
        "operation_scenarios": [
            {
                "scenario_class": c,
                "module_id": MODULE,
                "instruction_section": "correct_sequence",
                "expected_behavior": "reports what the response says and stops there",
                "expected_escalation": "none",
            }
            for c in SUPPLIED
        ],
        "coverage_declaration": {
            "modules_in_forge": 11,
            "modules_covered": 1,
            "modules_uncovered": [],
            "functions_in_module": 0,
            "agent_model": "ollama/llama3.1:8b",
            "functions_covered": 0,
        },
        "module_never_do": {MODULE: never_do},
        "module_not_applicable": {MODULE: DECLARED},
    }


async def test_the_curriculum_response_carries_no_probe_and_no_grading_key(
    client: AsyncClient,
) -> None:
    """The isolation claim, read out of the bytes the submitter receives — and stated as an
    INFORMATION claim rather than a string one, because the first draft of this test was wrong.

    The first draft asserted that no held-out field's value appears in the response. It failed, and
    the failure was the test's rather than the code's: `unsupported_subject` for the first
    prohibition is ``score: null``, which is a fragment of the submitter's own sentence, and that
    sentence is echoed back on `never_do_obligations` by design (path B's acknowledgement that the
    obligation was received and is outstanding). A substring of what the submitter sent cannot be a
    leak to the submitter.

    So the real claim, and the one asserted: **every held-out value that reaches the wire is one the
    submitter already had.** The parsed fragments — subject, forbidden readings, required disclosure
    — are derived from the submitter's sentence and carry nothing it did not write. What must never
    reach it is what SimForge ADDED: the probe, the two expectations, and the reference that ties a
    grade to an entry.
    """
    res = await client.post(
        "/api/operation/curriculum", json=_body(list(PORTFOLIO_HEALTH_NEVER_DO))
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    wire = json.dumps(payload)
    submitted = json.dumps(_body(list(PORTFOLIO_HEALTH_NEVER_DO)))

    authored = author_for_module(MODULE, PORTFOLIO_HEALTH_NEVER_DO)
    assert authored, "a vacuous set would make every assertion below true and measure nothing"
    assert held_out_fields(), "likewise: an empty field set would loop zero times and pass"

    for scenario in authored:
        for field_name in sorted(held_out_fields()):
            value = getattr(scenario, field_name)
            for text in value if isinstance(value, tuple) else [value]:
                if not isinstance(text, str) or len(text) <= 12:
                    continue
                if text in wire:
                    assert text in submitted, (
                        f"{field_name} reached the submitter carrying something the submitter did "
                        f"not send: {text!r}"
                    )

    # And the four SimForge ADDED, checked by name as well as by the loop above, so that a field
    # renamed out of `held_out_fields()` still fails here.
    for scenario in authored:
        assert scenario.probe not in wire
        assert scenario.expected_behavior not in wire
        assert scenario.expected_escalation not in wire
        assert scenario.obligation_ref not in wire

    assert payload["never_do_obligations"] == {MODULE: list(PORTFOLIO_HEALTH_NEVER_DO)}
    assert "probe" not in wire

    # "held_out" DOES appear once, and it must: `gate_9_5_flag` is the string that tells the caller
    # never to treat a held-out claim as self-proving, and surfacing it on every validation result
    # is what ADR-0048 requires. Everything else in the response is free of it.
    assert wire.count("held_out") == 1
    assert "held_out" in payload["gate_9_5_flag"]


async def test_the_response_names_neither_held_out_class_as_something_it_supplied(
    client: AsyncClient,
) -> None:
    """A submission that declares a never-do list is ACCEPTED and labelled `demonstrated`, and the
    response says nothing about scenarios SimForge is about to author. The submitter learns that its
    obligation was received and outstanding - which is the whole of path B - and not what will be
    put to the agent."""
    res = await client.post(
        "/api/operation/curriculum", json=_body(list(PORTFOLIO_HEALTH_NEVER_DO))
    )
    payload = res.json()

    assert payload["accepted"] is True
    assert payload["module_levels"][MODULE] == LEVEL_DEMONSTRATED
    assert set(payload["module_declared_absences"][MODULE]) == set(DECLARED)
    assert not set(payload["module_declared_absences"][MODULE]) & HELD_OUT_CLASSES
    assert "held_out_authoring_is_a_process_control" in payload["gate_9_5_flag"]


async def test_the_round_trip_moves_portfolio_health_off_demonstrated(
    client: AsyncClient,
) -> None:
    """End to end, and the level is computed from what the endpoint actually returned.

    Submit -> accepted at `demonstrated` -> take the `never_do_obligations` the response carries ->
    author the held-out set from them -> the same module classifies
    `certified_with_declared_absence`. Nothing here is a literal: the supplied classes come out of
    the response's own accounting and the held-out pair comes out of the pipeline.

    This is what P-06 was waiting for. Its declaration was correct and reasoned and could not move
    the level on its own, because the two classes it is forbidden to declare away were also the two
    nobody was authoring.
    """
    res = await client.post(
        "/api/operation/curriculum", json=_body(list(PORTFOLIO_HEALTH_NEVER_DO))
    )
    payload = res.json()
    assert payload["module_levels"][MODULE] == LEVEL_DEMONSTRATED

    obligations = payload["never_do_obligations"][MODULE]
    authored = authored_classes(author_for_module(MODULE, obligations))
    assert authored == HELD_OUT_CLASSES

    declared = set(payload["module_declared_absences"][MODULE])
    level = classify_certification_level(
        SUPPLIED, declared_not_applicable=declared, held_out_authored=authored
    )

    assert level == LEVEL_CERTIFIED_WITH_DECLARED_ABSENCE
    assert set(SUPPLIED) | declared | authored == set(ALL_SCENARIO_CLASSES), (
        "all nine accounted for: two supplied, five declared absent with a reason, two authored "
        "by SimForge - and not one of the nine merely absent"
    )


async def test_a_module_that_declares_no_never_do_list_is_unaffected(
    client: AsyncClient,
) -> None:
    """The pipeline adds no obligation where the module declared none.

    An empty never-do list is `never_do.STATUS_NONE` - genuinely not applicable, and it has been
    since FIX 2. A pipeline that authored a probe anyway would turn a correct absence into a
    manufactured obligation and hold a module at provisional for a rule it never had.
    """
    res = await client.post("/api/operation/curriculum", json=_body([]))
    payload = res.json()

    assert payload["accepted"] is True
    assert payload["never_do_obligations"] == {}
    assert author_for_module(MODULE, []) == ()
    assert authored_classes(author_for_module(MODULE, [])) == frozenset()
