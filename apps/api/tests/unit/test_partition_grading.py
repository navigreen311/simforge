"""ADR-0110 - grading a sealed partition: the pure parts, and what the agent sees."""

from __future__ import annotations

import dataclasses
import json

import pytest

from src.services.operation.battery import battery_system_context
from src.services.operation.held_out import author_for_module
from src.services.operation.held_out_scoring import (
    REASON_NOT_RUN,
    ScenarioVerdict,
    deliver,
)
from src.services.operation.partition_grading import (
    FAIL,
    NOT_RUN,
    PASS,
    ModulePlan,
    agent_verdict,
    put_partition,
    scenario_from_body,
    venture_of_run_ref,
)
from tests.unit.test_held_out_authoring import PORTFOLIO_HEALTH_NEVER_DO
from tests.unit.test_operation_battery import (
    _compliant,
    _imported_src_modules,
    _runtime,
    _violating,
)

MODULE = "portfolio_health"
AGENT = "agent-under-test"


def _scenarios():  # noqa: ANN202
    return author_for_module(MODULE, PORTFOLIO_HEALTH_NEVER_DO)


def _plan() -> ModulePlan:
    return ModulePlan(MODULE, tuple(_scenarios()), PORTFOLIO_HEALTH_NEVER_DO)


def _v(verdict: str) -> ScenarioVerdict:
    return ScenarioVerdict("m#1", "never_do_violation", verdict)


# --- the seam ------------------------------------------------------------


def test_a_body_written_as_json_reads_back_as_the_same_scenario() -> None:
    """The seam: asdict, through JSON, back. Tuples came back as lists."""
    for scenario in _scenarios():
        body = json.loads(json.dumps(dataclasses.asdict(scenario)))
        assert scenario_from_body(body) == scenario


def test_a_body_with_an_unknown_key_is_refused_not_guessed() -> None:
    body = dataclasses.asdict(_scenarios()[0]) | {"reason": "x"}
    with pytest.raises(TypeError):
        scenario_from_body(body)


# --- the venture ---------------------------------------------------------


def test_the_venture_is_segment_two_of_an_office_ref() -> None:
    ref = "office:greenstone:cre-forge:buyer_match@c8afb0e6:9fdc2096d73a:p6.0.0"
    assert venture_of_run_ref(ref) == "greenstone"


@pytest.mark.parametrize("ref", ["op-run-0102", "", "office::x:y", "other:greenstone:f:m"])
def test_a_ref_the_office_did_not_mint_names_no_venture(ref: str) -> None:
    assert venture_of_run_ref(ref) is None


# --- the fold ------------------------------------------------------------


def test_pass_only_if_every_scenario_passes() -> None:
    assert agent_verdict([_v("PASS")] * 5) == PASS
    assert agent_verdict([_v("PASS")] * 4 + [_v("FAIL")]) == FAIL


def test_nothing_put_is_not_run_never_a_pass() -> None:
    """A default is not evidence (ADR-0106)."""
    assert agent_verdict([]) == NOT_RUN


def test_a_probe_never_put_is_not_run_not_a_failure() -> None:
    not_run = ScenarioVerdict("m#1", "never_do_violation", "NOT_RUN", (REASON_NOT_RUN,))
    assert agent_verdict([_v("PASS"), not_run]) == NOT_RUN


def test_a_failure_outranks_a_probe_never_put() -> None:
    not_run = ScenarioVerdict("m#1", "never_do_violation", "NOT_RUN", (REASON_NOT_RUN,))
    assert agent_verdict([not_run, _v("FAIL")]) == FAIL


def test_the_verdict_is_a_bare_string_with_no_reason_on_it() -> None:
    """Whether, never why: the fold returns one word, not a verdict object."""
    assert isinstance(agent_verdict([_v("FAIL")]), str)


# --- putting it ----------------------------------------------------------


async def test_a_compliant_agent_passes_the_partition() -> None:
    runtime, _ = _runtime(_compliant)
    assert await put_partition(agent_id=AGENT, plans=[_plan()], runtime=runtime) == PASS


async def test_a_violating_agent_fails_it() -> None:
    """The direction that matters: a grader that always said PASS passes the test above."""
    runtime, _ = _runtime(_violating)
    assert await put_partition(agent_id=AGENT, plans=[_plan()], runtime=runtime) == FAIL


async def test_the_agent_receives_the_delivered_probe_and_nothing_else() -> None:
    """Each prompt is `deliver(scenario).prompt`, in order, one per scenario.
    The system context is the battery's own, byte for byte."""
    runtime, provider = _runtime(_compliant)
    await put_partition(agent_id=AGENT, plans=[_plan()], runtime=runtime)

    assert provider.prompts == [deliver(s).prompt for s in _scenarios()]
    context = battery_system_context(MODULE, PORTFOLIO_HEALTH_NEVER_DO)
    for system in provider.systems:
        assert system.endswith(context)
        for leaked in ("never_do_violation", "silent_failure", "held_out", "partition"):
            assert leaked not in system.lower()


async def test_a_provider_that_cannot_answer_is_not_run() -> None:
    def _boom(system: str, prompt: str) -> str:
        raise RuntimeError("provider down")

    runtime, _ = _runtime(_boom)
    assert await put_partition(agent_id=AGENT, plans=[_plan()], runtime=runtime) == NOT_RUN


async def test_an_answer_outside_the_grammar_is_not_observed() -> None:
    """ADR-0117: nothing could be read, so nothing was decided - NOT_RUN, not FAIL.

    ADR-0063 still fails this in the ordinary battery; the partition records it as
    a finding and neither passes nor fails the probe.
    """
    runtime, _ = _runtime(lambda s, p: "Sure, happy to help.")
    assert await put_partition(agent_id=AGENT, plans=[_plan()], runtime=runtime) == NOT_RUN


# --- ADR-0050 ------------------------------------------------------------


@pytest.mark.parametrize("router", ["src.routers.operation", "src.routers.office"])
def test_no_router_can_reach_the_partition_grader(router: str) -> None:
    """The grader holds the partition's content; a router that reached it
    could put it. The cadence router reaches `jobs`, so its trigger is
    refused inside the job instead - `test_partition_sweep` holds that."""
    reachable = _imported_src_modules(router)
    assert "src.services.operation.partition_grading" not in reachable
    assert "src.workers.partition_sweep" not in reachable
