"""P-05b — delivery, not retrieval: what the agent under test receives, and what it does not.

ADR-0050 refused the fetch endpoint P-05 asked for. **The consequence the ruling does not state, and
the thing these tests are really about: the battery has to run inside SimForge.** An external runner
cannot put a probe it cannot obtain, and the only way to obtain one would be the refused fetch. So
delivery is a function call — `held_out_scoring.run_held_out_battery` pushes each probe to a
caller-supplied `ask` and grades what comes back — and that is the only shape the ruling
leaves, not a shortcut around building an endpoint.

The third projection is added here. P-05 built two (submitter, and the graded result); ADR-0050
implies a third, for the agent under test, and it is the narrowest of the three.
"""

from __future__ import annotations

from dataclasses import fields

from src.services.operation.held_out import author_for_module
from src.services.operation.held_out_scoring import (
    ObservedBehaviour,
    Probe,
    deliver,
    run_held_out_battery,
)
from src.services.operation.rubric import VERDICT_FAIL, VERDICT_NOT_RUN, VERDICT_PASS
from tests.unit.test_held_out_authoring import PORTFOLIO_HEALTH_NEVER_DO

MODULE = "portfolio_health"


def _authored():
    return author_for_module(MODULE, PORTFOLIO_HEALTH_NEVER_DO)


# =================================================================================================
# What the agent under test receives
# =================================================================================================


def test_the_agent_receives_the_prompt_and_nothing_else() -> None:
    """Two fields. The ones that are missing are the test.

    No grading key, which is obvious. **No scenario class**, which is not — and it is the one that
    would have been added by accident. An agent told "this is the never_do_violation scenario" is
    being examined on recognising a format, not on holding the line when a colleague has a good
    reason and will be inconvenienced by a no. The probe is written to read like an ordinary
    request; one label would undo the whole construction.
    """
    assert {f.name for f in fields(Probe)} == {"module_id", "prompt"}

    for scenario in _authored():
        probe = deliver(scenario)
        assert probe.prompt == scenario.probe
        assert probe.module_id == scenario.module_id

        rendered = repr(probe)
        assert scenario.scenario_class not in rendered
        assert scenario.obligation_ref not in rendered
        assert scenario.expected_behavior not in rendered
        assert scenario.expected_escalation not in rendered
        if scenario.prohibited_action:
            assert scenario.prohibited_action not in rendered


def test_the_probe_cannot_be_told_apart_by_class_from_the_probe_alone() -> None:
    """Both classes deliver into the same two-field shape, so a battery cannot sort the probes into
    "refusal cases" and "concealment cases" and neither can whatever it hands them to."""
    delivered = [deliver(s) for s in _authored()]
    classes = {s.scenario_class for s in _authored()}

    assert len(classes) == 2, "portfolio_health authors both classes - this is not vacuous"
    assert all(isinstance(p, Probe) for p in delivered)
    assert all(len(fields(p)) == 2 for p in delivered)


def test_a_probe_is_deliberately_not_serialisable_into_a_response() -> None:
    """There is no `to_dict`, no `model_dump`, and no pydantic model anywhere near `Probe`.

    A probe that could be serialised is one route away from being returned by one, and ADR-0050 is
    that no route returns one. If a probe ever needs to cross a process boundary that is a new
    decision and it belongs in a new ADR, not in a serialiser somebody added because it was handy.
    """
    probe = deliver(_authored()[0])

    assert not hasattr(probe, "to_dict")
    assert not hasattr(probe, "model_dump")
    assert not hasattr(probe, "dict")
    assert not hasattr(probe, "json")


# =================================================================================================
# The direction: pushed, one at a time, and never enumerable
# =================================================================================================


def test_the_battery_pushes_probes_and_is_never_handed_the_set() -> None:
    """`ask` is called BY the battery; nothing calls the battery to be given the scenarios.

    A caller holds an agent and receives questions. It sees every probe in turn — it must, they are
    the questions — but it sees them as they are asked, one at a time and mediated, and what it
    returns is the agent's behaviour rather than the scenario. The grading key never leaves the
    module: the verdict below is computed against a `HeldOutScenario` this caller never held.
    """
    scenarios = _authored()
    seen: list[Probe] = []

    def ask(probe: Probe) -> ObservedBehaviour:
        seen.append(probe)
        return ObservedBehaviour(escalated=True)

    grading = run_held_out_battery(MODULE, scenarios, ask)

    assert len(seen) == len(scenarios) == 12
    assert all(isinstance(p, Probe) for p in seen)
    assert grading.module_id == MODULE
    assert len(grading.verdicts) == 12


def test_a_compliant_agent_still_passes_through_the_delivery_path() -> None:
    """The grading P-05 proved is unchanged by delivery; this asserts the two compose rather than
    re-deriving the grader's behaviour."""
    scenarios = _authored()
    by_prompt = {s.probe: s for s in scenarios}

    def ask(probe: Probe) -> ObservedBehaviour:
        scenario = by_prompt[probe.prompt]
        if scenario.scenario_class == "never_do_violation":
            return ObservedBehaviour(refused=frozenset({scenario.obligation_ref}))
        return ObservedBehaviour(
            assertions=frozenset({(scenario.unsupported_subject or "", "as returned")}),
            disclosed=frozenset(),
        )

    grading = run_held_out_battery(MODULE, scenarios, ask)

    assert grading.passed
    assert all(r["verdict"] == VERDICT_PASS for r in grading.rubric_results)


def test_a_violating_agent_fails_through_the_delivery_path() -> None:
    """The agent does what it was asked, having been given no signal that it should not."""
    scenarios = _authored()
    by_prompt = {s.probe: s for s in scenarios}

    def ask(probe: Probe) -> ObservedBehaviour:
        scenario = by_prompt[probe.prompt]
        if scenario.scenario_class == "never_do_violation":
            return ObservedBehaviour(actions_taken=frozenset({scenario.obligation_ref}))
        reading = (
            scenario.unsupported_readings[0] if scenario.unsupported_readings else "the headline"
        )
        return ObservedBehaviour(
            assertions=frozenset({(scenario.unsupported_subject or "", reading)})
        )

    grading = run_held_out_battery(MODULE, scenarios, ask)

    assert not grading.passed
    assert all(r["verdict"] == VERDICT_FAIL for r in grading.rubric_results)


def test_a_probe_the_battery_could_not_put_is_NOT_RUN_and_closes_nothing() -> None:
    """`ask` returning `None` means the probe could not be put. A battery that half-ran must produce
    a result that reads as half-run — reporting the unaskable as a pass is the shape of every bug
    this subsystem exists to refuse."""
    scenarios = _authored()

    def ask(probe: Probe) -> ObservedBehaviour | None:
        return None

    grading = run_held_out_battery(MODULE, scenarios, ask)

    assert grading.exercised_refs == frozenset()
    assert all(v.verdict == VERDICT_NOT_RUN for v in grading.verdicts)
    assert all(r["verdict"] == VERDICT_NOT_RUN for r in grading.rubric_results)
    assert not grading.passed


def test_delivery_is_in_process_and_has_no_wire_format() -> None:
    """The consequence of ADR-0050, asserted rather than left in a docstring.

    No inbound payload carries an observation, because a runner that could report one would have had
    to be handed the probes first — and it cannot be. If a field named for held-out observations
    ever appears on `GateResultRequest`, the fetch has come back under another name and this test is
    where that should surface.

    The first draft of this test asserted no inbound field name contains "observed" and FAILED on
    `failure_modes_observed`, which is a pre-existing field about what a run saw and has nothing to
    do with held-out delivery. The assertion was too loose, not the code wrong: what must be absent
    is a field carrying a PROBE or an observation OF one, so the check names those rather than a
    word that legitimately appears elsewhere.
    """
    from src.schemas import operation_payloads as payloads

    forbidden = {"probe", "probes", "held_out", "held_out_observations", "observed_behaviour"}
    for model_name in ("AgentRunOutcome", "GateResultRequest", "ForgeOperationCurriculum"):
        model = getattr(payloads, model_name)
        names = set(model.model_fields)
        assert names, f"{model_name} has no fields - a vacuous loop would pass this"
        assert not (names & forbidden), (
            f"{model_name} carries {sorted(names & forbidden)}. A probe or an observation of "
            f"one on "
            f"an inbound payload means the fetch ADR-0050 refused has returned under another name."
        )
        for field_name in names:
            assert "probe" not in field_name
            assert "held_out" not in field_name
