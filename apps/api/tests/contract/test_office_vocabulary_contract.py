"""office_vocabulary contract: SimForge (provider) ↔ The Office (consumer).

Three mismatches between these two systems were found by reading rather than by CI, and
every one of them failed in a way that looked like success:

  1. SimForge emits `provisional`; The Office's CHECK constraint knew seven states, so
     the insert would have failed at runtime, on a real certification.
  2. The Office maps TIMEOUT to `in_training` so that a hung run can never certify —
     but SimForge emits no TIMEOUT, so the mapping was unreachable and a hung run
     resolved to nothing at all.
  3. `not_applicable` is a real SimForge dimension verdict that no manifest declared.

This is the check that catches the fourth.

HOW THE TWO COPIES STAY IN STEP
===============================

    The canonical contract lives in The Office at `broker/simforge_contract.json`. This
    repository holds a copy at `docs/contracts/office-simforge-contract.json`, and this
    test asserts SimForge's own enums against it.

    The Office asserts the same file against its constants, its migration and its
    response manifest. Neither side imports the other — they are separate applications
    and stay that way — so the file is the contract and `contract_version` is what says
    the copies are the same generation.

    Adding a state or a verdict on either side without updating both copies fails here,
    or there, or both. That is the point.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.operation.gate_verdict import (
    GATE_VERDICT_TO_STATE,
    GateVerdict,
    is_assignable_verdict,
    verdict_for_finished_state,
)
from src.services.operation.scenarios import ALL_SCENARIO_CLASSES
from src.services.operation.state_machine import (
    OPERATION_STATES,
    OperationState,
    is_assignable,
)

CONTRACT_FILE = (
    Path(__file__).resolve().parents[4] / "docs" / "contracts" / "office-simforge-contract.json"
)

#: Bump on BOTH sides together. A mismatch means one copy was updated and the other was
#: not, which is the exact failure this file exists to make loud.
EXPECTED_CONTRACT_VERSION = "2.0.0"


@pytest.fixture(scope="module")
def contract() -> dict:
    assert CONTRACT_FILE.exists(), (
        f"{CONTRACT_FILE} is missing. The Office/SimForge vocabulary contract must be "
        "checked in on both sides; without it nothing detects a divergence."
    )
    with CONTRACT_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def declared_states(contract: dict) -> set[str]:
    return {k for k in contract["certification_states"] if not k.startswith("_")}


def test_the_copies_are_the_same_generation(contract: dict) -> None:
    assert contract["contract_version"] == EXPECTED_CONTRACT_VERSION, (
        "the contract file's version and this test's expectation disagree. Either the "
        "contract changed and this test was not updated, or the copy from The Office "
        "was not taken."
    )


def test_every_state_simforge_can_emit_is_storable_by_the_office(
    declared_states: set[str],
) -> None:
    """The mismatch that would have failed at runtime, on a certification.

    A state SimForge emits and The Office's CHECK constraint rejects is not a warning
    and not a degraded mode — it is an INSERT that raises, in production, at the moment
    an agent is being certified.
    """
    emitted = set(OPERATION_STATES)
    unstorable = emitted - declared_states
    assert not unstorable, (
        f"SimForge can emit state(s) {sorted(unstorable)} that the Office contract does "
        "not declare. Add them to the contract on BOTH sides (and to migration 0029's "
        "CHECK constraint), or stop emitting them."
    )


def test_provisional_is_declared_and_agreed_to_be_unassignable(contract: dict) -> None:
    """`provisional` survives only if both sides agree what it means.

    SimForge withholds assignability locally (`is_assignable`). The Office withholds it
    by requiring `certified` in `resolve_grant`. Both must say so, because a state one
    side treats as a hold and the other treats as a pass is worse than no state at all.
    """
    assert OperationState.PROVISIONAL.value == "provisional"
    assert not is_assignable(OperationState.PROVISIONAL)

    spec = contract["certification_states"]["provisional"]
    assert spec["assignable"] is False
    assert "WITHHELD" in spec["meaning"]


def test_certified_is_the_only_assignable_state_on_both_sides(contract: dict) -> None:
    assignable_here = {s for s in OPERATION_STATES if is_assignable(s)}
    assignable_in_contract = {
        name
        for name, spec in contract["certification_states"].items()
        if not name.startswith("_") and spec["assignable"]
    }
    assert assignable_here == assignable_in_contract == {"certified"}


def test_a_provisional_cert_records_what_it_ran_against(contract: dict) -> None:
    """The Office refuses a provisional result with no basis. SimForge must send one.

    A hold whose instruction hash is unknown cannot be recomputed and cannot be
    cleared, so it would be permanent by accident — the same defect the `certified`
    basis rule exists to prevent, one state over.
    """
    basis = contract["certification_states"]["provisional"]["requires_basis"]
    assert "instruction_content_hash" in basis
    assert "forge_api_version" in basis
    # Deliberately absent: certification was withheld, so there is no certified tier,
    # and a placeholder is a number a later reader takes for a real cap.
    assert "certified_tier" not in basis


def test_not_applicable_is_declared_as_not_crossing_the_boundary(contract: dict) -> None:
    """`not_applicable` is real, it is ours, and it stops here.

    It is a per-dimension verdict inside a rubric result. The Office's response manifest
    carries no rubric results at all, deliberately — a rich enough explanation of a
    failure reconstructs the scenario that produced it. Declaring that here makes the
    absence intentional rather than an oversight somebody later "fixes".
    """
    rubric = contract["rubric_result_verdicts"]
    assert "not_applicable" in rubric["values"]
    assert rubric["crosses_office_boundary"] is False
    assert "not a zero" in rubric["not_applicable_note"]


def test_the_office_holds_the_timeout_deadline(contract: dict) -> None:
    """The half of the timeout fix that is NOT SimForge's, written down.

    SimForge reports a run it observes exceeding its window. It cannot report a run
    whose worker died — a dead process announces nothing — so The Office holds a
    deadline on unanswered submissions. Both halves, because either alone has a hole.
    """
    timeout = contract["timeout"]
    assert timeout["never_resolves_to"] == "certified"
    assert timeout["resolves_to"] == "in_training"
    assert timeout["office_default_deadline_hours"] > 0
    assert "died" in timeout["detected_by_office_when"]


def test_trust_tiers_match(contract: dict) -> None:
    """SimForge sets `max_certified_trust_tier`; the Office caps the declared tier with
    it. A tier one side can send and the other cannot rank is an uncappable grant."""
    assert contract["trust_tiers"]["values"] == ["suggest", "propose", "auto_execute"]


def test_the_nine_scenario_classes_are_still_nine() -> None:
    """Not a vocabulary The Office reads, and asserted here anyway.

    Coverage across these nine is what separates a `certified` module from a
    `demonstrated` one, and a class quietly disappearing would shrink the denominator
    rather than fail anything.
    """
    assert len(ALL_SCENARIO_CLASSES) == 9
    assert "never_do_violation" in ALL_SCENARIO_CLASSES
    assert "silent_failure" in ALL_SCENARIO_CLASSES


def test_the_verdict_table_is_the_same_table_on_both_sides(contract: dict) -> None:
    """Mismatch #2, now checkable.

    The Office handled a TIMEOUT verdict SimForge never sent. The mapping was correct
    and unreachable, which is the worst combination: nothing failed, nothing fired, and
    a hung battery resolved to nothing at all. SimForge now has the same table, and this
    is what keeps the two copies one table rather than two that happen to agree today.
    """
    declared = {k: v for k, v in contract["gate_verdicts"].items() if not k.startswith("_")}
    assert GATE_VERDICT_TO_STATE == declared, (
        "SimForge's gate_verdict.GATE_VERDICT_TO_STATE and the shared contract disagree. "
        "A verdict one side emits and the other cannot map is exactly the class of "
        "mismatch this file exists to catch; update BOTH copies."
    )
    assert {v.value for v in GateVerdict} == set(declared)


def test_simforge_can_actually_emit_timeout(contract: dict) -> None:
    """The point of the whole exercise, stated as an assertion.

    Not "TIMEOUT is mapped" — it was always mapped. The claim is that TIMEOUT is a value
    SimForge's own vocabulary contains and can therefore reach.
    """
    assert GateVerdict.TIMEOUT.value in GATE_VERDICT_TO_STATE
    assert contract["timeout"]["emitted_by_simforge_when"]


def test_timeout_never_resolves_to_a_pass(contract: dict) -> None:
    """Part 10.1, on the emitting side.

    Asserted against `is_assignable_verdict` rather than by reading the table, because
    the property that matters is not "TIMEOUT maps to in_training" but "a timed-out run
    can never permit a Forge call" — which stays true if the intermediate state is ever
    renamed.
    """
    assert not is_assignable_verdict(GateVerdict.TIMEOUT.value)
    assert GATE_VERDICT_TO_STATE[GateVerdict.TIMEOUT.value] != OperationState.CERTIFIED.value
    assert GATE_VERDICT_TO_STATE[GateVerdict.TIMEOUT.value] == contract["timeout"]["resolves_to"]
    assert contract["timeout"]["never_resolves_to"] == OperationState.CERTIFIED.value


def test_a_timed_out_run_is_not_reported_as_a_failure() -> None:
    """`failed` means the agent ran and did not pass. A cut-off run proved nothing.

    The two verdicts are adjacent enough that collapsing them would look like a tidy-up,
    and it would quietly defame every agent whose battery was interrupted.
    """
    assert (
        GATE_VERDICT_TO_STATE[GateVerdict.TIMEOUT.value]
        != GATE_VERDICT_TO_STATE[GateVerdict.FAIL.value]
    )
    assert GATE_VERDICT_TO_STATE[GateVerdict.TIMEOUT.value] != OperationState.FAILED.value


def test_pass_is_the_only_verdict_that_permits_a_forge_call() -> None:
    assignable = {v for v in GATE_VERDICT_TO_STATE if is_assignable_verdict(v)}
    assert assignable == {GateVerdict.PASS.value}


def test_a_state_a_run_cannot_produce_is_refused_rather_than_defaulted() -> None:
    """A silent default in the state → verdict direction is how a non-outcome becomes a PASS.

    `stale_instructions` is something that happens to a cert AFTER it was earned, not an
    outcome a run produced. Asking for its verdict is a bug, and it raises.
    """
    with pytest.raises(ValueError, match="not a state a finished operation run"):
        verdict_for_finished_state(OperationState.STALE_INSTRUCTIONS.value)
    with pytest.raises(ValueError):
        verdict_for_finished_state(OperationState.IN_TRAINING.value)
