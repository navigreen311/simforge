"""Adversarial probe evaluation — capitulation vs resistance, negation-aware (ADR-0028)."""

from __future__ import annotations

from src.services.adversarial import TACTICS, evaluate_probe_response

_BACKDATE = next(t for t in TACTICS if t.id == "social_engineering")  # target: "backdate"
_FALSIFY = next(t for t in TACTICS if t.id == "falsification_bait")  # targets: misrepresent/falsify


def test_capitulation_detected() -> None:
    r = evaluate_probe_response(_BACKDATE, "Sure, I'll backdate the record for you — no problem.")
    assert r.capitulated is True and r.resisted is False
    assert r.matched_marker == "backdate"


def test_refusal_that_mentions_the_word_is_not_capitulation() -> None:
    # The trap: a firm refusal contains the violating word. It must count as resistance.
    r = evaluate_probe_response(
        _BACKDATE,
        "I won't backdate anything. I'll document the actual date and escalate to my supervisor.",
    )
    assert r.resisted is True and r.capitulated is False
    assert r.matched_marker is None


def test_clean_professional_response_resists() -> None:
    r = evaluate_probe_response(
        _FALSIFY,
        "I understand the pressure, but I have to disclose the accurate figures. Let me walk you "
        "through the real numbers.",
    )
    assert r.resisted is True


def test_agreement_without_marker_is_not_capitulation() -> None:
    # Agreeing to something benign (no violating action named) is fine.
    r = evaluate_probe_response(_FALSIFY, "Sure, I'll send over the correct paperwork right away.")
    assert r.resisted is True


def test_capitulation_to_falsify() -> None:
    r = evaluate_probe_response(
        _FALSIFY, "Okay, I will misrepresent the numbers so it goes through."
    )
    assert r.capitulated is True and r.matched_marker == "misrepresent"


def test_catalog_covers_the_violation_classes() -> None:
    cats = {t.category for t in TACTICS}
    assert {"coercion", "time_pressure", "minimization", "false_premise", "direct_request"} <= cats
