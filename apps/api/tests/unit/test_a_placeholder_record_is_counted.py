"""ADR-0151: a template where a value belongs is counted, never graded.

`<count>`, `[the number as reported in the response]` pass silent_failure - they assert no
forbidden reading - so the count is the only place they show: the battery's attempt records
and the partition's outcome findings, summed by `partition_report`.
"""

from __future__ import annotations

import pytest

from src.services.operation import battery as B
from src.services.operation.held_out import author_for_module
from tests.unit.test_held_out_authoring import PORTFOLIO_HEALTH_NEVER_DO
from tests.unit.test_operation_battery import _compliant, _runtime

MODULE = "portfolio_health"


@pytest.mark.parametrize(
    "claim",
    [
        "<count>",
        "<anomaly_count_value>",
        "<specific gate that was refused>",
        "[the number as reported in the response]",
        "an anomaly count of <n>",
    ],
)
def test_a_template_is_a_placeholder(claim: str) -> None:
    assert B.is_placeholder_record(("s", claim))


@pytest.mark.parametrize(
    "claim",
    ["0", "9 of 12", "NOT KNOWN", "a <= b", "x < 5 and y > 3", "[3, 4]", "ALL SEVERITIES"],
)
def test_a_value_is_not(claim: str) -> None:
    assert not B.is_placeholder_record(("s", claim))


def test_no_record_is_not_a_placeholder() -> None:
    assert not B.is_placeholder_record(None)


def _templating(system: str, prompt: str) -> str:
    """Compliant, except every over-read probe records a template."""
    silent = {
        s.probe
        for s in author_for_module(MODULE, PORTFOLIO_HEALTH_NEVER_DO)
        if s.scenario_class == "silent_failure"
    }
    if prompt in silent:
        return "ACT: PROCEED\nRECORD: the figure = <count>"
    return _compliant(system, prompt)


async def test_the_battery_counts_them_and_still_passes() -> None:
    runtime, _ = _runtime(_templating)
    report = await B.run_module_battery(
        module_id=MODULE,
        agent_id="agent-under-test",
        never_do=PORTFOLIO_HEALTH_NEVER_DO,
        runtime=runtime,
    )
    silent = [
        s
        for s in author_for_module(MODULE, PORTFOLIO_HEALTH_NEVER_DO)
        if s.scenario_class == "silent_failure"
    ]
    assert report.placeholder_records == len(silent)
    assert report.passed  # counted, never graded
    exam = B.ExamReport.of(report)
    assert exam.attempt_records[0]["placeholder_records"] == len(silent)
