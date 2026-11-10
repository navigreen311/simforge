"""ADR-0166 stage 2: the synthetic CRE world and its tasks, for one seed."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
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
    World,
    comps_found,
    export_json,
    export_world,
    forge_differs,
    generate_tasks,
    generate_world,
    render_page,
    tasks_digest,
    world_digest,
    world_name,
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
        assert all(b["email"] == f"{b['key']}@sandbox.invalid" for b in w.buyers)


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


# --- the export, in CRE Forge's loader format (stage 5) ----------------------------------------

#: medlink-wholesale `app/sandbox/loader.py` NAMESPACE, written out here, not imported.
CRE_LOADER_NAMESPACE = uuid.UUID("5a4d0c66-0166-4e2b-9b1a-5a4db0c0ffee")
#: CRE Forge's enums as of medlink-wholesale 90fadc6 (`app/models/*.py`).
CRE_ENUMS = {
    "property_type": {
        "commercial",
        "industrial",
        "retail",
        "office",
        "mixed_use",
        "land",
        "multifamily",
    },
    "property_status": {
        "new",
        "researching",
        "contacted",
        "qualified",
        "negotiating",
        "under_contract",
        "assignment_executed",
        "closing",
    },
    "deal_status": {
        "prospect",
        "negotiating",
        "verbal_agreement",
        "under_contract",
        "due_diligence",
        "closing",
        "assignment_executed",
        "closed",
    },
    "deal_stage": {"acquisition", "disposition"},
    "buyer_type": {"investor", "flipper", "landlord", "developer", "owner_occupant", "wholesaler"},
    "buyer_status": {"active", "inactive", "vip", "blacklisted"},
    "financing_type": {"cash", "hard_money", "conventional", "creative"},
}
#: The keys the loader reads without a default.
LOADER_REQUIRES = {
    "properties": {
        "key",
        "address",
        "city",
        "state",
        "zip_code",
        "property_type",
        "status",
        "comps",
    },
    "comps": {"address", "days_ago", "sale_price", "distance_miles", "similarity_score"},
    "deals": {"key", "property", "deal_name", "status", "stage"},
    "buyers": {"key", "name", "buyer_type", "status", "financing_type"},
}


def test_every_id_is_the_one_cre_forges_loader_gives_its_key() -> None:
    for seed in SEEDS:
        w = generate_world(seed)
        assert world_name(seed) == f"simforge-{GENERATOR_VERSION}-seed-{seed}"
        for kind in KINDS:
            for r in getattr(w, kind):
                want = uuid.uuid5(CRE_LOADER_NAMESPACE, f"{world_name(seed)}/{r['key']}")
                assert r["id"] == str(want)


def test_the_export_is_the_world_in_the_loaders_format() -> None:
    for seed in SEEDS:
        w = generate_world(seed)
        e = export_world(w)
        assert e["world"] == world_name(seed)
        assert e["world_digest"] == world_digest(w)
        assert [p["key"] for p in e["properties"]] == [p["key"] for p in w.properties]
        assert [d["key"] for d in e["deals"]] == [d["key"] for d in w.deals]
        assert [b["key"] for b in e["buyers"]] == [b["key"] for b in w.buyers]
        for kind, rows in (
            ("properties", e["properties"]),
            ("deals", e["deals"]),
            ("buyers", e["buyers"]),
        ):
            for r in rows:
                assert LOADER_REQUIRES[kind] <= set(r), (kind, LOADER_REQUIRES[kind] - set(r))
        by_key = {p["key"]: p for p in w.properties}
        comps = {c["key"]: c for c in w.sales_comps}
        exported = 0
        for p in e["properties"]:
            assert p["property_type"] in CRE_ENUMS["property_type"]
            assert p["status"] in CRE_ENUMS["property_status"]
            src = by_key[p["key"]]
            assert p["asking_price"] == (
                None if src["asking_price"] is None else str(src["asking_price"])
            )
            for i, c in enumerate(p["comps"]):
                # The loader keys a comp by its place under its subject.
                mine = comps[f"{p['key']}/comp-{i}"]
                assert mine["subject_property_id"] == src["id"]
                assert LOADER_REQUIRES["comps"] <= set(c)
                assert c["days_ago"] == mine["sale_age_days"]
                assert Decimal(c["distance_miles"]) == Decimal(str(mine["distance_mi"]))
                assert Decimal(c["sale_price"]) == mine["sale_price"]
                exported += 1
        assert exported == len(w.sales_comps)
        for d in e["deals"]:
            assert d["property"] in by_key
            assert d["status"] in CRE_ENUMS["deal_status"]
            assert d["stage"] in CRE_ENUMS["deal_stage"]
        for b in e["buyers"]:
            assert b["buyer_type"] in CRE_ENUMS["buyer_type"]
            assert b["status"] in CRE_ENUMS["buyer_status"]
            assert b["financing_type"] in CRE_ENUMS["financing_type"]


def test_the_export_is_the_same_bytes_for_the_same_seed() -> None:
    assert export_json(4) == export_json(4)
    assert json.loads(export_json(4)) == export_world(generate_world(4))
    assert export_json(4) != export_json(5)


def test_comps_are_counted_the_way_the_sandbox_forge_counts_them() -> None:
    """The source reads the 2 * max_comps nearest inside the radius; only then does age drop."""
    subject = generate_world(0).properties[0]

    def comp(key: str, distance: float, age: int) -> dict:
        return {
            "key": key,
            "id": key,
            "subject_property_id": subject["id"],
            "distance_mi": distance,
            "sale_age_days": age,
        }

    w = World(
        seed=0,
        generator_version=GENERATOR_VERSION,
        properties=(subject,),
        sales_comps=(comp("a", 0.5, 900), comp("b", 0.6, 900), comp("c", 1.5, 30)),
        buyers=(),
        deals=(),
    )
    # The two nearest are both too old, so the recent one at 1.5 mi is never read.
    assert comps_found(w, subject["id"], radius_mi=2.0, max_age_days=365, max_comps=1) == 0
    assert comps_found(w, subject["id"], radius_mi=2.0, max_age_days=365, max_comps=2) == 1


def test_the_page_script_writes_the_export(tmp_path: Path) -> None:
    from scripts.sandbox_world_page import main

    assert main(["--seed", "7", "--out", str(tmp_path), "--export"]) == 0
    path = tmp_path / f"{world_name(7)}.json"
    assert path.read_bytes() == export_json(7).encode()


def test_the_forges_answer_is_read_as_an_agent_reads_it() -> None:
    """`forge_fields` takes the Forge's response: null counts come off `results`."""
    tasks = _tasks(0)
    nulls = next(t for t in tasks if any(k.startswith("results_with_") for k in t.forge_answer))
    (key,) = (k for k in nulls.forge_answer if k.startswith("results_with_"))
    field = key[len("results_with_") : -len("_null")]
    want = nulls.forge_answer[key]
    rows = [{field: None}] * want + [{field: 1}] * (nulls.forge_answer["total"] - want)
    response = {**{k: v for k, v in nulls.forge_answer.items() if k != key}, "results": rows}
    assert forge_differs(nulls, response) == []
    assert forge_differs(nulls, {**response, "results": rows[1:]}) == [key]

    missing = next(t for t in tasks if t.forge_answer.get("status") == 404)
    # The body CRE Forge's `app_exception_handler` returns, as the sandbox Forge returned it.
    body = {"success": False, "data": None, "error": missing.forge_answer["error"], "details": {}}
    assert forge_differs(missing, {"status": 404, **body}) == []
    assert forge_differs(missing, {"status": 200, **body}) == ["status"]
