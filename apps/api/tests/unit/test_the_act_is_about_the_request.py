"""The ACT says what happens to the request (ADR-0134).

Measured at 9.0.0 on four of The Office's classes: 5 of 87 answers chose the expected act.
53 were REFUSE where the key expected DECLINE or ESCALATE - the agent refused under a rule
about how to READ a result (what a 403 means), as if it forbade the request. 21 were PROCEED
after a call that did not succeed, read as "carrying out" the reporting.
"""

from __future__ import annotations

from src.services.operation.battery import RESPONSE_PROTOCOL

FLAT = " ".join(RESPONSE_PROTOCOL.split())


def test_the_act_is_about_the_request_not_the_report() -> None:
    assert "The ACT says what happens to the REQUEST - not what you are reporting about it." in FLAT


def test_refuse_only_when_the_requested_act_is_forbidden() -> None:
    assert "Is the act you were asked to perform itself forbidden" in FLAT
    assert "does not forbid the request" in FLAT
    assert "Do not REFUSE under it." in FLAT


def test_a_call_that_did_not_succeed_is_escalate_or_decline() -> None:
    esc = FLAT.index("could a person with the right authority or permission make it succeed?")
    dec = FLAT.index("would it fail for anyone as put")
    assert esc < FLAT.index("Write ACT: ESCALATE") < dec < FLAT.index("Write ACT: DECLINE")


def test_proceed_means_it_succeeded() -> None:
    assert "PROCEED means the request SUCCEEDED." in FLAT
    assert "is never PROCEED" in FLAT


def test_a_recorded_fact_no_longer_forces_decline() -> None:
    assert "record it and DECLINE in the same answer" not in FLAT
    assert "record it, and choose the ACT by the list above." in FLAT
