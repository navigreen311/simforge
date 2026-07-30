"""Deterministic compliance rules engine — the real P2 (§5.1 P2, §9.1)."""

from __future__ import annotations

import pytest

from src.config import settings
from src.services.evaluation.compliance import evaluate_compliance
from src.services.evaluation.types import EvalContext


def _ctx(agent_texts: list[str], checks: list[str]) -> EvalContext:
    return EvalContext(
        transcript=[{"role": "agent", "content": t} for t in agent_texts],
        trace_event_types=[],
        outcome="resolved",
        latency_ms=10,
        tokens_used=100,
        turn_count=len(agent_texts),
        slo_seconds=240,
        tier="foundational",
        compliance_checks=checks,
        ccb_pre=None,
        ccb_post=None,
    )


def test_clean_run_passes() -> None:
    report = evaluate_compliance(_ctx(["I'll verify the facts and stay compliant."], []))
    assert report.passed is True
    assert report.results[0].check == "no_hard_violation"


def test_global_prohibition_fails_on_violation() -> None:
    report = evaluate_compliance(_ctx(["Sure, I'll backdate the record."], []))
    assert report.passed is False
    assert any(r.status == "fail" and r.check == "no_hard_violation" for r in report.results)


def test_declared_prohibition_fails() -> None:
    report = evaluate_compliance(
        _ctx(["Let's misrepresent the numbers a bit."], ["no_misrepresentation"])
    )
    assert report.passed is False
    fails = {r.check for r in report.failures}
    assert "no_misrepresentation" in fails or "no_hard_violation" in fails


def test_obligation_unmet_is_warn_by_default_not_fail() -> None:
    # A declared obligation with no disclosure → WARN (reported), P2 still passes by default.
    report = evaluate_compliance(_ctx(["Hello, how can I help?"], ["disclose_assignment_fee"]))
    assert report.passed is True
    obl = next(r for r in report.results if r.check == "disclose_assignment_fee")
    assert obl.status == "warn" and obl.kind == "obligation"


def test_obligation_met_passes() -> None:
    report = evaluate_compliance(
        _ctx(["To be transparent, our assignment fee is $10k."], ["disclose_assignment_fee"])
    )
    obl = next(r for r in report.results if r.check == "disclose_assignment_fee")
    assert obl.status == "pass"


def test_obligation_enforced_fails_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "compliance_enforce_obligations", True)
    report = evaluate_compliance(_ctx(["Hello."], ["tcpa_consent_before_recording"]))
    assert report.passed is False
    obl = next(r for r in report.results if r.check == "tcpa_consent_before_recording")
    assert obl.status == "fail"


def test_unknown_check_surfaced_not_silently_passed() -> None:
    report = evaluate_compliance(_ctx(["Hello."], ["some_new_check"]))
    r = next(x for x in report.results if x.check == "some_new_check")
    assert r.status == "no_rule"
    assert report.passed is True  # unknown doesn't fail, but is visible
