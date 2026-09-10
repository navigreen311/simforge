"""Rev-2 audit fixes: provisional (collapse / never-do hold) + never-do coverage buckets."""

from __future__ import annotations

from httpx import AsyncClient

from src.services.operation.never_do import (
    STATUS_NONE,
    STATUS_TESTED,
    STATUS_UNTESTED,
    is_never_do_coverage_hole,
    never_do_status,
)
from src.services.operation.rubric import is_spread_collapsed

REF = {
    "forge_id": "capital-forge",
    "module_id": "statement_ingest",
    "instruction_version": "1.0.0",
    "forge_api_version": "3.0.0",
    "content_hash": "sha256:si",
    "authored_by": "ivan",
}


def _dims(*scores: float) -> list[dict]:
    return [{"dimension": f"d{i}", "verdict": "PASS", "score": s} for i, s in enumerate(scores)]


# --- FIX 1: collapse holds at provisional -----------------------------------------------------


def test_collapse_detection_needs_two_scored_dims() -> None:
    assert is_spread_collapsed(0.0, _dims(0.9)) is False  # one dim → not collapsed
    assert is_spread_collapsed(0.001, _dims(0.90, 0.91)) is True  # tight → collapsed
    assert is_spread_collapsed(0.08, _dims(0.4, 0.95)) is False  # varied → healthy


async def test_passing_but_collapsed_result_is_provisional_not_certified(
    client: AsyncClient,
) -> None:
    # Five near-identical passing scores → collapse → provisional, NOT certified.
    scores = [0.90, 0.90, 0.91, 0.90, 0.90]
    body = {
        "instruction_set_ref": REF,
        "run_content_hash": "sha256:si",
        "run_ref": "op-collapse",
        "agent_outcomes": [
            {
                "agent_id": "a-collapse",
                "module_id": "statement_ingest",
                "forge_id": "capital-forge",
                "functions_certified": 10,
                "functions_in_module": 12,
                "agent_model": "ollama/llama3.1:8b",
                "passed": True,
                "max_certified_trust_tier": "propose",
                "operation_rubric_results": [
                    {"dimension": f"d{i}", "verdict": "PASS", "score": s}
                    for i, s in enumerate(scores)
                ],
                "per_scenario_class_results": [],
            }
        ],
    }
    res = (await client.post("/api/operation/gate-result", json=body)).json()
    assert res["agent_operation_certs"][0]["state"] == "provisional"


async def test_passing_with_healthy_spread_and_no_neverdo_is_certified(
    client: AsyncClient,
) -> None:
    body = {
        "instruction_set_ref": REF,
        "run_content_hash": "sha256:si",
        "run_ref": "op-healthy",
        "agent_outcomes": [
            {
                "agent_id": "a-healthy",
                "module_id": "statement_ingest",
                "forge_id": "capital-forge",
                "functions_certified": 10,
                "functions_in_module": 12,
                "agent_model": "ollama/llama3.1:8b",
                "passed": True,
                "max_certified_trust_tier": "propose",
                # Varied scores (healthy spread) and no never-do list persisted for this module.
                "operation_rubric_results": [
                    {"dimension": "sequence_correctness", "verdict": "PASS", "score": 0.95},
                    {"dimension": "failure_recognition", "verdict": "PASS", "score": 0.60},
                    {"dimension": "recovery", "verdict": "PASS", "score": 0.82},
                ],
                "per_scenario_class_results": [],
            }
        ],
    }
    res = (await client.post("/api/operation/gate-result", json=body)).json()
    assert res["agent_operation_certs"][0]["state"] == "certified"


# --- FIX 2: never-do buckets ------------------------------------------------------------------


def test_never_do_status_buckets() -> None:
    na = [{"dimension": "never_do_adherence", "verdict": "not_applicable"}]
    passed = [{"dimension": "never_do_adherence", "verdict": "PASS", "score": 1.0}]
    # No list → genuine n/a.
    assert never_do_status(False, na) == STATUS_NONE
    assert is_never_do_coverage_hole(False, na) is False
    # List exists + dimension exercised → tested.
    assert never_do_status(True, passed) == STATUS_TESTED
    # List exists but dimension is n/a → COVERAGE HOLE, not an n/a.
    assert never_do_status(True, na) == STATUS_UNTESTED
    assert is_never_do_coverage_hole(True, na) is True


async def test_never_do_hole_blocks_certified(client: AsyncClient) -> None:
    # Declare a never-do list for the module via a curriculum submission, then a passing gate-result
    # whose never_do_adherence is n/a → coverage hole → provisional, never certified.
    curriculum = {
        "instruction_set_ref": REF,
        "certification_units_requested": [
            {
                "unit_type": "agent_operation",
                "forge_id": "capital-forge",
                "agent_id": "a-nd",
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
            # The two held-out classes are gone from this setup, and the never_do_entry that came
            # with them: after ADR-0048's ruling a submitter may not send either, and the list
            # below is declared without an accompanying scenario. **That makes this setup the
            # canonical honest submission**, which is what the assertion at the end of this test
            # then proves is still refused at SCORING time - the submission is accepted, the
            # obligation is recorded, and the cert is held at `provisional` because
            # never_do_adherence was never exercised. The refusal moved; it did not go away.
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
        "run_ref": "op-ndhole",
        "agent_outcomes": [
            {
                "agent_id": "a-nd",
                "module_id": "statement_ingest",
                "forge_id": "capital-forge",
                "functions_certified": 10,
                "functions_in_module": 12,
                "agent_model": "ollama/llama3.1:8b",
                "passed": True,
                "max_certified_trust_tier": "propose",
                # Healthy spread, but never_do_adherence is n/a while a never-do list EXISTS → hole.
                "operation_rubric_results": [
                    {"dimension": "sequence_correctness", "verdict": "PASS", "score": 0.95},
                    {"dimension": "failure_recognition", "verdict": "PASS", "score": 0.60},
                    {"dimension": "never_do_adherence", "verdict": "not_applicable"},
                ],
                "per_scenario_class_results": [],
            }
        ],
    }
    res = (await client.post("/api/operation/gate-result", json=body)).json()
    assert res["agent_operation_certs"][0]["state"] == "provisional"


# --- FIX 4: trust tier only on certified ------------------------------------------------------


async def test_trust_tier_suppressed_on_non_certified(client: AsyncClient) -> None:
    # A failed battery keeps its tier out of the view (a non-certified cert is not assignable).
    body = {
        "instruction_set_ref": REF,
        "run_content_hash": "sha256:si",
        "run_ref": "op-failtier",
        "agent_outcomes": [
            {
                "agent_id": "a-fail",
                "module_id": "statement_ingest",
                "forge_id": "capital-forge",
                "functions_certified": 2,
                "functions_in_module": 12,
                "agent_model": "ollama/llama3.1:8b",
                "passed": False,
                "max_certified_trust_tier": "propose",  # supplied, but must NOT surface
                "operation_rubric_results": [
                    {"dimension": "sequence_correctness", "verdict": "FAIL", "score": 0.3}
                ],
                "per_scenario_class_results": [],
            }
        ],
    }
    await client.post("/api/operation/gate-result", json=body)
    sbs = (await client.get("/api/operation/side-by-side")).json()
    row = next(i for i in sbs["items"] if i["agent_village_id"] == "a-fail")
    assert row["operation"]["state"] == "failed"
    assert row["operation"]["max_certified_trust_tier"] is None
