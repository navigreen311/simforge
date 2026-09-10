"""A run in which the agent answered NOTHING readably must not certify (ADR-0052).

Written first as a CHARACTERISATION, before any amendment, to establish what the code did rather
than what it was believed to do. It did certify: three of these four tests passed against the old
gate, and this file is left in place with its expectations corrected so the gap cannot reopen
quietly. `battery.FAILURE_MODE_UNREADABLE` says an unreadable answer *"is not evidence the
agent did the forbidden thing"*, and `BatteryReport.passed` is deliberately not `grading.passed`
so that a battery which could not be run is not a battery the agent failed.

The property under test is the other direction: **an unreadable answer must never become a PASS.**
On the never-do path that is held by exactly one mechanism — `is_never_do_coverage_hole`. These
tests ask what holds it when there is no never-do list to hang a hole on.
"""

from __future__ import annotations

from httpx import AsyncClient

from src.services.operation.never_do import is_never_do_coverage_hole
from src.services.operation.rubric import (
    compute_rubric_dimension_spread,
    is_evidence_absent,
    is_spread_collapsed,
)

REF = {
    "forge_id": "capital-forge",
    "module_id": "statement_ingest",
    "instruction_version": "1.0.0",
    "forge_api_version": "3.0.0",
    "content_hash": "sha256:si",
    "authored_by": "ivan",
}

# What the battery reports when every answer was unreadable: the probes were put, nothing was
# observed, so every dimension the battery would have written carries NOT_RUN and no score.
ALL_NOT_RUN = [
    {"dimension": "sequence_correctness", "verdict": "NOT_RUN"},
    {"dimension": "failure_recognition", "verdict": "NOT_RUN"},
    {"dimension": "escalation_discipline", "verdict": "NOT_RUN"},
    {"dimension": "recovery", "verdict": "NOT_RUN"},
]


def _outcome(agent_id: str, results: list[dict]) -> dict:
    return {
        "agent_id": agent_id,
        "module_id": "statement_ingest",
        "forge_id": "capital-forge",
        "functions_certified": 10,
        "functions_in_module": 12,
        "agent_model": "ollama/llama3.1:8b",
        # `BatteryReport.passed` is `not any(FAIL)`. Every verdict is NOT_RUN, so there is no FAIL
        # and the battery reports passed=True. This is the real value, not a convenient one.
        "passed": True,
        "max_certified_trust_tier": "propose",
        "operation_rubric_results": results,
        "per_scenario_class_results": [],
        "failure_modes_observed": ["agent_answer_did_not_conform_to_the_response_protocol"],
    }


# --- the two guards, asked directly ------------------------------------------------------------


def test_the_two_original_guards_still_abstain_and_the_third_one_catches_it() -> None:
    """Both ORIGINAL withholding paths abstain, for reasons that are individually correct.

    `is_spread_collapsed` needs >= 2 dimensions carrying PASS/FAIL to have anything to compare;
    NOT_RUN dimensions carry no score, so the count is 0 and it short-circuits. That is right:
    nothing was measured, so nothing collapsed.

    `is_never_do_coverage_hole` is False because no never-do list was declared — `STATUS_NONE`,
    a genuine n/a. Also right: there is no obligation to have left unexercised.
    """
    spread = compute_rubric_dimension_spread(ALL_NOT_RUN)
    assert spread == 0.0, "no scored dimensions -> spread is 0.0 by definition"
    assert is_spread_collapsed(spread, ALL_NOT_RUN) is False
    assert is_never_do_coverage_hole(False, ALL_NOT_RUN) is False

    # Two correct abstentions, and the outcome used to be `certified`. The third withhold states
    # the property directly instead of relying on a never-do list to carry it.
    assert is_evidence_absent(ALL_NOT_RUN) is True


# --- the same thing through the endpoint that decides the state ---------------------------------


async def test_unreadable_throughout_with_no_never_do_list_is_held_at_provisional(
    client: AsyncClient,
) -> None:
    """The reproduction, with the expectation it should always have had.

    No never-do list, every dimension NOT_RUN, nothing observed at all. This returned `certified`
    before ADR-0052 — a certification asserting that something passed, over a run that observed
    nothing.
    """
    body = {
        "instruction_set_ref": REF,
        "run_content_hash": "sha256:si",
        "run_ref": "op-unreadable-no-neverdo",
        "agent_outcomes": [_outcome("a-unreadable", ALL_NOT_RUN)],
    }
    res = (await client.post("/api/operation/gate-result", json=body)).json()
    state = res["agent_operation_certs"][0]["state"]
    assert state == "provisional", f"nothing was observed; got {state!r}"


async def test_the_degenerate_shape_no_rubric_results_at_all(client: AsyncClient) -> None:
    """A module with no obligations authors no probes, so the grading carries no dimensions."""
    body = {
        "instruction_set_ref": REF,
        "run_content_hash": "sha256:si",
        "run_ref": "op-unreadable-empty",
        "agent_outcomes": [_outcome("a-empty", [])],
    }
    res = (await client.post("/api/operation/gate-result", json=body)).json()
    state = res["agent_operation_certs"][0]["state"]
    assert state == "provisional", f"nothing was observed; got {state!r}"


# --- the half of the property that does hold ----------------------------------------------------


async def test_the_same_run_with_a_never_do_list_is_held_at_provisional(
    client: AsyncClient,
) -> None:
    """The contrast, and the reason the gap is easy to miss.

    Identical outcome shape plus a declared never-do list and a NOT_RUN `never_do_adherence`:
    the coverage hole fires and the unit is held. The property is not absent — it is carried
    entirely by the never-do list, and a module without one is outside its reach.
    """
    curriculum = {
        "instruction_set_ref": REF,
        "certification_units_requested": [
            {
                "unit_type": "agent_operation",
                "forge_id": "capital-forge",
                "agent_id": "a-unreadable-nd",
                "module_id": "statement_ingest",
            }
        ],
        "operation_scenarios": [
            {
                "scenario_class": c,
                "module_id": "statement_ingest",
                "instruction_section": f"s.{c}",
                "expected_behavior": "b",
                "expected_escalation": "e",
            }
            for c in (
                "happy_path",
                "malformed_input",
                "partial_failure",
                "rate_limited",
                "permission_denied",
                "escalation_required",
                "recovery_after_failure",
            )
        ],
        "coverage_declaration": {
            "modules_in_forge": 3,
            "modules_covered": 1,
            "modules_uncovered": [],
            "functions_in_module": 12,
            "agent_model": "ollama/llama3.1:8b",
            "functions_covered": 10,
        },
        "module_never_do": {"statement_ingest": ["overwrite_prior_statement"]},
    }
    acc = await client.post("/api/operation/curriculum", json=curriculum)
    assert acc.status_code == 200, acc.text

    body = {
        "instruction_set_ref": REF,
        "run_content_hash": "sha256:si",
        "run_ref": "op-unreadable-with-neverdo",
        "agent_outcomes": [
            _outcome(
                "a-unreadable-nd",
                [*ALL_NOT_RUN, {"dimension": "never_do_adherence", "verdict": "NOT_RUN"}],
            )
        ],
    }
    res = (await client.post("/api/operation/gate-result", json=body)).json()
    state = res["agent_operation_certs"][0]["state"]
    assert state == "provisional", f"the never-do hole should hold this; got {state!r}"
