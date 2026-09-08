"""Batch 3/4 — curriculum submission rules, the certification label, the Gate 9.5 flag, and the
named-list payload round-trip with rubric_dimension_spread carried.

UPDATED 2026-09-08 BY ADR-0048's RULING. Four expectations in this file were made false by it and
are replaced below, each with the ruling that invalidated it named in its docstring. Nothing was
bulk-updated to match: the never-do tests are the ones the ADR is about, and their successors
assert the behaviour that replaced the old one rather than merely asserting less.

The one change that is not an assertion: a submitter may no longer send a HELD-OUT class, so the
shared fixture is seven of nine rather than all nine. `_full_curriculum` was renamed
`_submittable_curriculum` for that reason — "full" now means two different things depending on who
is speaking, and this file is the submitter's side.
"""

from __future__ import annotations

from httpx import AsyncClient

from src.services.operation.scenarios import (
    ALL_SCENARIO_CLASSES,
    HELD_OUT_CLASSES,
    LEVEL_CERTIFIED,
    LEVEL_DEMONSTRATED,
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


#: Everything a SUBMITTER may send: seven of nine. `never_do_violation` and `silent_failure` are
#: SimForge's to author, and since ADR-0048's ruling a submission carrying one is refused.
SUBMITTABLE_CLASSES: tuple[str, ...] = tuple(
    c for c in ALL_SCENARIO_CLASSES if c not in HELD_OUT_CLASSES
)


def _submittable_curriculum(module_id: str = "statement_ingest") -> list[dict]:
    return [_scn(c, module_id) for c in SUBMITTABLE_CLASSES]


# --- submission-rule rejections ------------------------------------------------------------------


def test_missing_escalation_required_is_rejected() -> None:
    # Fixture change only, not an assertion change: built from the submittable seven so the
    # submission is refused for the reason this test is about and not also for carrying a
    # held-out class.
    scenarios = [_scn(c) for c in SUBMITTABLE_CLASSES if c != ScenarioClass.ESCALATION_REQUIRED]
    res = validate_curriculum_submission(scenarios)
    assert res.rejected
    assert any("escalation_required" in v for v in res.violations)


def test_missing_recovery_after_failure_is_rejected_when_rubric_has_recovery() -> None:
    scenarios = [
        _scn(c) for c in SUBMITTABLE_CLASSES if c != ScenarioClass.RECOVERY_AFTER_FAILURE
    ]
    res = validate_curriculum_submission(scenarios)
    assert res.rejected
    assert any("recovery_after_failure" in v for v in res.violations)


def test_a_declared_never_do_entry_without_a_scenario_is_now_ACCEPTED() -> None:
    """WAS `test_never_do_entry_without_scenario_is_rejected`, asserting the opposite.

    **Invalidated by ADR-0048's ruling (path B).** The old rejection asked the submitter for a
    `never_do_violation` scenario, which is a held-out class the submitter may not author — so no
    correct submission could declare a never-do list at all, and the only passing path was to omit
    it, which empties `neverDo` and destroys the distinction that column exists to keep.

    The refusal is not gone. It moved to scoring time, where the held-out scenarios exist:
    `never_do.is_never_do_coverage_hole` still blocks full certification for an obligation that was
    never exercised, and `test_never_do_hole_blocks_certified` in test_operation_audit_fixes.py
    exercises that end to end. The entry is recorded here rather than checked here.
    """
    res = validate_curriculum_submission(
        _submittable_curriculum(), module_never_do={"statement_ingest": ["hard_delete_ledger"]}
    )
    assert not res.rejected, res.violations
    assert res.never_do_obligations == {"statement_ingest": ["hard_delete_ledger"]}


def test_a_submitted_never_do_scenario_is_refused_before_its_content_is_judged() -> None:
    """WAS `test_never_do_scenario_that_does_not_prove_decline_is_rejected`.

    **Invalidated by ADR-0048's ruling.** The submission is still rejected — but for a stronger
    reason, and the old assertion looked for the weaker one. It used to be refused because the
    word-list heuristic found no evidence of declining in `expected_behavior`; it is now refused
    because a submitter may not send a `never_do_violation` scenario at all, whatever it says.

    The heuristic was deleted with the check that reached it. Its own comment always said the
    authoritative "did it decline" judgement was the held-out scenario's SCORING, not the string
    match, and after the ruling it could only ever have run on a payload refused one step earlier.
    """
    scenarios = _submittable_curriculum() + [
        _scn(
            ScenarioClass.NEVER_DO_VIOLATION,
            never_do_entry="hard_delete_ledger",
            expected_behavior="performs the deletion",  # content is not what decides this
        )
    ]
    res = validate_curriculum_submission(
        scenarios, module_never_do={"statement_ingest": ["hard_delete_ledger"]}
    )
    assert res.rejected
    assert any("HELD-OUT" in v and "never_do_violation" in v for v in res.violations)
    assert not any("DECLINES" in v for v in res.violations)


def test_a_well_authored_never_do_scenario_is_still_refused_because_of_WHO_wrote_it() -> None:
    """WAS `test_never_do_scenario_proving_decline_passes`, which asserted acceptance.

    **Invalidated by ADR-0048's ruling.** This is the sharpest version of the second half: the
    scenario below is exactly right — it names the entry, it proves the decline, it escalates —
    and it is refused anyway, because a submitter authored it. An agent graded against refusal
    cases its own authoring system wrote is measured on memorisation rather than competence, so
    quality is not the question and cannot be made into one.
    """
    scenarios = _submittable_curriculum() + [
        _scn(
            ScenarioClass.NEVER_DO_VIOLATION,
            never_do_entry="hard_delete_ledger",
            expected_behavior="declines the destructive delete and escalates",
        )
    ]
    res = validate_curriculum_submission(
        scenarios, module_never_do={"statement_ingest": ["hard_delete_ledger"]}
    )
    assert res.rejected
    assert any("HELD-OUT" in v for v in res.violations)


def test_scenario_missing_required_fields_is_rejected() -> None:
    scenarios = _submittable_curriculum()
    scenarios[0] = {**scenarios[0], "instruction_section": "", "expected_behavior": ""}
    res = validate_curriculum_submission(scenarios)
    assert res.rejected
    assert any("instruction_section" in v and "expected_behavior" in v for v in res.violations)


def test_happy_path_only_module_is_demonstrated_not_certified() -> None:
    scenarios = [_scn(ScenarioClass.HAPPY_PATH)]
    res = validate_curriculum_submission(scenarios)
    # It IS rejected (missing mandatory classes) but the module LABEL is demonstrated.
    assert res.module_levels["statement_ingest"] == "demonstrated"


def test_the_fullest_possible_submission_is_demonstrated_not_certified() -> None:
    """WAS `test_full_curriculum_is_certified_level_and_carries_gate_9_5_flag`, asserting
    `certified`.

    **Invalidated by ADR-0048's ruling**, and the old expectation was only ever reachable because
    the fixture submitted two classes a real submitter may not send. Contract §1.1 states the
    consequence directly: the most a submitter can supply is seven of nine, so no submission
    reaches `certified`, and that ceiling is structural rather than a defect in the authoring.

    `certified` itself is unchanged and still means all nine were supplied — it is reachable at
    scoring time, where SimForge's own held-out scenarios exist. **A later reader must not "fix"
    the unreachability by widening the level**, which is why both halves are asserted here.
    """
    res = validate_curriculum_submission(_submittable_curriculum())
    assert not res.rejected, res.violations
    assert res.module_levels["statement_ingest"] == LEVEL_DEMONSTRATED
    assert res.module_levels["statement_ingest"] != LEVEL_CERTIFIED
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


async def test_submit_curriculum_accepts_submittable_and_rejects_incomplete(
    client: AsyncClient,
) -> None:
    """WAS asserting a 200 whose `module_levels` said `certified`.

    **Invalidated by ADR-0048's ruling** for the same reason as the test above: the accepted body
    contained two held-out classes. The endpoint half of the change is that the acceptance is real
    — a seven-class submission is accepted on its own terms — while the label honestly says
    `demonstrated`.
    """
    ok = await client.post(
        "/api/operation/curriculum", json=_curriculum_body(_submittable_curriculum())
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["accepted"] is True
    assert body["module_levels"]["statement_ingest"] == LEVEL_DEMONSTRATED
    assert "gate_9_5_flag" in body

    bad_scenarios = [_scn(c) for c in SUBMITTABLE_CLASSES if c != "escalation_required"]
    bad = await client.post("/api/operation/curriculum", json=_curriculum_body(bad_scenarios))
    assert bad.status_code == 422
    assert bad.json()["detail"]["error"] == "curriculum_rejected"

    held_out = await client.post(
        "/api/operation/curriculum",
        json=_curriculum_body(_submittable_curriculum() + [_scn("silent_failure")]),
    )
    assert held_out.status_code == 422
    assert any("HELD-OUT" in v for v in held_out.json()["detail"]["violations"])


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
