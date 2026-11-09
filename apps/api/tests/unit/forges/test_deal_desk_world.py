"""ADR-0166 stage 2: the synthetic CRE world and its tasks, for one seed."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.forges.deal_desk import DealDeskEngine
from src.services.forges.deal_desk_world import (
    COMP_AGE_DAYS,
    COMP_RADIUS_MI,
    GENERATOR_VERSION,
    READ_MODULES,
    TASK_CLASSES,
    Task,
    TurnKey,
    generate_tasks,
    generate_world,
    render_page,
    tasks_digest,
    world_digest,
)
from src.services.operation.battery import AgentAnswer
from src.services.operation.rubric import VERDICT_FAIL, VERDICT_PASS
from src.services.operation.scenarios import HELD_OUT_CLASSES
from src.services.operation.submitted_scoring import (
    REASON_CLAIM_MISMATCH,
    REASON_WITHHELD,
    SubmittedKey,
    grade_submitted,
)

SEEDS = range(50)
#: Ruled for the schedule (ADR-0166, 9 November): at most 60 tasks per run.
MAX_TASKS_PER_RUN = 60
KINDS = ("properties", "sales_comps", "buyers", "deals")


def _key(k: TurnKey) -> SubmittedKey:
    return SubmittedKey(
        scenario_class=k.scenario_class,
        module_id=k.module_id,
        instruction_section=k.instruction_section,
        ordinal=k.ordinal,
        situation=k.situation,
        expected_act=k.expected_act,
        expected_record=k.expected_record,
        record_subject=k.record_subject,
        record_claim=k.record_claim,
        record_claim_options=k.record_claim_options,
        expected_caveat=k.expected_caveat,
        acceptable_acts=k.acceptable_acts,
    )


def _right(k: TurnKey) -> AgentAnswer:
    return AgentAnswer(
        act=k.expected_act,
        record=(k.record_subject, k.record_claim or "") if k.record_subject else None,
        caveats=("as expected",) if k.expected_caveat else (),
    )


def _tasks(seed: int) -> tuple[Task, ...]:
    return generate_tasks(generate_world(seed))


def test_the_same_seed_gives_the_same_world_tasks_and_page() -> None:
    for seed in (0, 1, 2, 41):
        assert world_digest(generate_world(seed)) == world_digest(generate_world(seed))
        assert tasks_digest(_tasks(seed)) == tasks_digest(_tasks(seed))
        assert render_page(seed) == render_page(seed)


def test_another_seed_gives_another_world() -> None:
    assert len({world_digest(generate_world(s)) for s in SEEDS}) == len(SEEDS)


def test_every_row_is_marked_synthetic_with_its_seed() -> None:
    for seed in SEEDS:
        w = generate_world(seed)
        for kind in KINDS:
            rows = getattr(w, kind)
            assert rows, kind
            for r in rows:
                assert r["synthetic"] is True
                assert r["seed"] == seed
                assert r["generator_version"] == GENERATOR_VERSION
        assert all(b["email"].endswith("@synthetic.invalid") for b in w.buyers)


def test_ids_are_unique_within_a_world() -> None:
    for seed in SEEDS:
        w = generate_world(seed)
        ids = [r["id"] for kind in KINDS for r in getattr(w, kind)]
        assert len(ids) == len(set(ids))


def test_tasks_cover_the_three_read_modules_and_no_held_out_class() -> None:
    forbidden = set(HELD_OUT_CLASSES) | {"permitted_request"}
    for seed in SEEDS:
        tasks = _tasks(seed)
        assert 0 < len(tasks) <= MAX_TASKS_PER_RUN
        assert {t.module_id for t in tasks} == set(READ_MODULES)
        classes = {t.scenario_class for t in tasks}
        assert classes <= set(TASK_CLASSES)
        assert not classes & forbidden
        assert len({t.task_id for t in tasks}) == len(tasks)


def test_grade_submitted_grades_every_expected_answer_unchanged() -> None:
    """Written as an approved key is written: the right answer passes, a wrong one fails."""
    for seed in (0, 1, 2):
        for t in _tasks(seed):
            for turn in (t.turn_a, t.turn_b):
                key = _key(turn)
                assert key.gradable and key.puttable
                assert grade_submitted(key, _right(turn)).verdict == VERDICT_PASS, t.task_id

            # Turn A: a request filed in good order and not carried out is withheld.
            if t.turn_a.acceptable_acts is None:
                withheld = grade_submitted(_key(t.turn_a), AgentAnswer(act="DECLINE"))
                assert withheld.verdict == VERDICT_FAIL
                assert REASON_WITHHELD in withheld.reasons

            # Turn B: a wrong count is a mismatch.
            if t.turn_b.record_subject and not t.turn_b.record_claim_options:
                wrong = AgentAnswer(
                    act=t.turn_b.expected_act,
                    record=(t.turn_b.record_subject, f"{t.turn_b.record_claim}1"),
                    caveats=("c",),
                )
                verdict = grade_submitted(_key(t.turn_b), wrong)
                assert verdict.verdict == VERDICT_FAIL
                assert REASON_CLAIM_MISMATCH in verdict.reasons


def test_comp_distances_and_ages_sit_away_from_every_bound() -> None:
    """The few days between loading and running cannot move a comp across a bound."""
    for seed in SEEDS:
        for c in generate_world(seed).sales_comps:
            default, cap = COMP_RADIUS_MI[c["property_type"]]
            assert abs(c["distance_mi"] - default) >= 0.1
            assert abs(c["distance_mi"] - cap) >= 0.1
            for bound in COMP_AGE_DAYS:
                assert abs(c["sale_age_days"] - bound) >= 35


def test_the_predicted_answers_follow_the_forge_rules() -> None:
    tasks = _tasks(0)
    pl = [t for t in tasks if t.module_id == "property_lookup"]
    assert any((t.turn_b.record_subject, t.turn_b.record_claim) == ("page_size", "100") for t in pl)
    bm = [t for t in tasks if t.module_id == "buyer_match"]
    high = [t for t in bm if t.scenario_class == "partial_failure"]
    assert high[0].forge_answer == {"status": 200, "total": 0, "suppressed": 2}
    statuses = {
        t.forge_answer["status"]
        for t in tasks
        if t.module_id == "comp_analysis" and t.scenario_class == "malformed_input"
    }
    assert statuses == {404, 422}


def test_the_page_lists_the_world_and_every_task() -> None:
    page = render_page(3)
    w = generate_world(3)
    for kind in KINDS:
        for r in getattr(w, kind):
            assert r["id"] in page
    for t in generate_tasks(w):
        assert t.task_id in page
    assert world_digest(w) in page
    assert "NOT ALL ROWS" not in page


def test_the_engine_seeds_a_world() -> None:
    e = DealDeskEngine()
    tenant = e.provision("run-sandbox")
    world = e.seed_world(tenant.tenant_id, 5)
    assert world_digest(world) == world_digest(generate_world(5))
    assert e.world_state(tenant.tenant_id)["synthetic_world"] == {"seed": 5, **world.counts()}
    assert e.audit_log(tenant.tenant_id)[-1]["action"] == "seed_world"


@pytest.mark.parametrize("seed", [0, 13])
def test_a_page_per_seed_is_written(tmp_path: Path, seed: int) -> None:
    from scripts.sandbox_world_page import main

    assert main(["--seed", str(seed), "--out", str(tmp_path)]) == 0
    assert (tmp_path / f"world-seed-{seed}.html").read_bytes() == render_page(seed).encode()
