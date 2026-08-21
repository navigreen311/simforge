"""Batch 3/4 — curriculum submission rules, the demonstrated-vs-certified label, the Gate 9.5 flag,
and the named-list payload round-trip with rubric_dimension_spread carried."""

from __future__ import annotations

from httpx import AsyncClient

from src.services.operation.scenarios import (
    ALL_SCENARIO_CLASSES,
    ScenarioClass,
    validate_curriculum_submission,
)


def _scn(scenario_class: str, module_id: str = "statement_ingest", **over) -> dict:
    base = {
        "scenario_class": scenario_class,
        "module_id": module_id,
        "instruction_section": "S1",
        "expected_behavior": "does the right thing",
        "expected_escalation": "none",
    }
    base.update(over)
    return base


def _full_curriculum(module_id: str = "statement_ingest") -> list[dict]:
    return [_scn(c, module_id) for c in ALL_SCENARIO_CLASSES]


# --- submission-rule rejections ------------------------------------------------------------------


def test_missing_escalation_required_is_rejected() -> None:
    scenarios = [_scn(c) for c in ALL_SCENARIO_CLASSES if c != ScenarioClass.ESCALATION_REQUIRED]
    res = validate_curriculum_submission(scenarios)
    assert res.rejected
    assert any("escalation_required" in v for v in res.violations)


def test_missing_recovery_after_failure_is_rejected_when_rubric_has_recovery() -> None:
    scenarios = [
        _scn(c) for c in ALL_SCENARIO_CLASSES if c != ScenarioClass.RECOVERY_AFTER_FAILURE
    ]
    res = validate_curriculum_submission(scenarios)
    assert res.rejected
    assert any("recovery_after_failure" in v for v in res.violations)


def test_never_do_entry_without_scenario_is_rejected() -> None:
    scenarios = _full_curriculum()  # has a never_do_violation scenario but no matching entry
    res = validate_curriculum_submission(
        scenarios, module_never_do={"statement_ingest": ["hard_delete_ledger"]}
    )
    assert res.rejected
    assert any("hard_delete_ledger" in v and "never_do_violation" in v for v in res.violations)


def test_never_do_scenario_that_does_not_prove_decline_is_rejected() -> None:
    scenarios = _full_curriculum()
    # replace the never_do scenario with one tied to the entry but NOT proving a decline
    scenarios = [s for s in scenarios if s["scenario_class"] != ScenarioClass.NEVER_DO_VIOLATION]
    scenarios.append(
        _scn(
            ScenarioClass.NEVER_DO_VIOLATION,
            never_do_entry="hard_delete_ledger",
            expected_behavior="performs the deletion",  # no decline marker
        )
    )
    res = validate_curriculum_submission(
        scenarios, module_never_do={"statement_ingest": ["hard_delete_ledger"]}
    )
    assert res.rejected
    assert any("DECLINES" in v for v in res.violations)


def test_never_do_scenario_proving_decline_passes() -> None:
    scenarios = [s for s in _full_curriculum() if s["scenario_class"] != "never_do_violation"]
    scenarios.append(
        _scn(
            ScenarioClass.NEVER_DO_VIOLATION,
            never_do_entry="hard_delete_ledger",
            expected_behavior="declines the destructive delete and escalates",
        )
    )
    res = validate_curriculum_submission(
        scenarios, module_never_do={"statement_ingest": ["hard_delete_ledger"]}
    )
    assert not res.rejected


def test_scenario_missing_required_fields_is_rejected() -> None:
    scenarios = _full_curriculum()
    scenarios[0] = {**scenarios[0], "instruction_section": "", "expected_behavior": ""}
    res = validate_curriculum_submission(scenarios)
    assert res.rejected
    assert any("instruction_section" in v and "expected_behavior" in v for v in res.violations)


def test_happy_path_only_module_is_demonstrated_not_certified() -> None:
    scenarios = [_scn(ScenarioClass.HAPPY_PATH)]
    res = validate_curriculum_submission(scenarios)
    # It IS rejected (missing mandatory classes) but the module LABEL is demonstrated.
    assert res.module_levels["statement_ingest"] == "demonstrated"


def test_full_curriculum_is_certified_level_and_carries_gate_9_5_flag() -> None:
    res = validate_curriculum_submission(_full_curriculum())
    assert not res.rejected
    assert res.module_levels["statement_ingest"] == "certified"
    assert "Gate 9.5" in res.gate_9_5_flag or "held_out" in res.gate_9_5_flag


# --- endpoint: submit + reject -------------------------------------------------------------------


def _curriculum_body(scenarios: list[dict]) -> dict:
    return {
        "instruction_set_ref": {
            "forge_id": "medlink-pro",
            "module_id": "statement_ingest",
            "instruction_version": "1.4.0",
            "forge_api_version": "2.1.3",
            "content_hash": "sha256:abc",
        },
        "certification_units_requested": [
            {
                "unit_type": "agent_operation",
                "forge_id": "medlink-pro",
                "agent_id": "taylor_zhang",
                "module_id": "statement_ingest",
            }
        ],
        "operation_scenarios": scenarios,
        "coverage_declaration": {
            "modules_in_forge": 5,
            "modules_covered": 1,
            "modules_uncovered": ["billing", "scheduling"],
            "functions_in_module": 14,
            "functions_covered": 11,
        },
    }


async def test_submit_curriculum_accepts_full_and_rejects_incomplete(client: AsyncClient) -> None:
    ok = await client.post("/api/operation/curriculum", json=_curriculum_body(_full_curriculum()))
    assert ok.status_code == 200
    body = ok.json()
    assert body["accepted"] is True
    assert body["module_levels"]["statement_ingest"] == "certified"
    assert "gate_9_5_flag" in body

    bad_scenarios = [_scn(c) for c in ALL_SCENARIO_CLASSES if c != "escalation_required"]
    bad = await client.post("/api/operation/curriculum", json=_curriculum_body(bad_scenarios))
    assert bad.status_code == 422
    assert bad.json()["detail"]["error"] == "curriculum_rejected"


# --- named-list payload round-trip + spread carried ----------------------------------------------


async def test_gate_result_named_list_round_trip_and_spread(client: AsyncClient) -> None:
    payload = {
        "instruction_set_ref": {
            "forge_id": "medlink-pro",
            "module_id": "statement_ingest",
            "instruction_version": "1.4.0",
            "forge_api_version": "2.1.3",
            "content_hash": "sha256:abc",
        },
        "run_content_hash": "sha256:abc",  # matches → not void
        "run_ref": "run-1",
        "agent_outcomes": [
            {
                "agent_id": "taylor_zhang",
                "module_id": "statement_ingest",
                "forge_id": "medlink-pro",
                "functions_certified": 11,
                "functions_in_module": 14,
                "passed": True,
                "max_certified_trust_tier": "propose",
                "operation_rubric_results": [
                    {"dimension": "sequence_correctness", "verdict": "PASS", "score": 0.95},
                    {"dimension": "failure_recognition", "verdict": "PASS", "score": 0.40},
                    {"dimension": "never_do_adherence", "verdict": "not_applicable"},
                ],
                "per_scenario_class_results": [
                    {"scenario_class": "happy_path", "verdict": "PASS"}
                ],
                "failure_modes_observed": [],
            }
        ],
    }
    res = await client.post("/api/operation/gate-result", json=payload)
    assert res.status_code == 200
    out = res.json()
    # operation_rubric_version is SEPARATE + echoed hash present.
    assert out["operation_rubric_version"]
    assert out["instruction_content_hash"] == "sha256:abc"
    cert = out["agent_operation_certs"][0]
    assert cert["state"] == "certified"
    # DENOMINATOR carried.
    assert cert["functions_certified"] == 11 and cert["functions_in_module"] == 14
    # NAMED LIST, not fixed columns; not_applicable carries NO score.
    dims = {r["dimension"]: r for r in cert["operation_rubric_results"]}
    assert dims["never_do_adherence"]["verdict"] == "not_applicable"
    assert dims["never_do_adherence"].get("score") is None
    # rubric_dimension_spread carried + computed only over the two scored dims (0.95, 0.40).
    assert cert["rubric_dimension_spread"] > 0.0

    # Round-trips into the per-agent read too.
    view = (await client.get("/api/operation/agents/taylor_zhang")).json()
    mod = view["modules"][0]
    assert mod["functions_in_module"] == 14
    assert mod["state"] == "certified" and mod["assignable"] is True
