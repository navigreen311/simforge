"""Unit tests for the 15-dim rubric + readiness gate."""

from __future__ import annotations

from src.services.evaluation.gate import check_readiness_gate
from src.services.evaluation.rubric import evaluate_rubric
from src.services.evaluation.types import EvalContext

_TIERS = {"F": 0.70, "I": 0.80, "AC": 0.85}


def _ccb(valence: float = 0.62, arc_phase: str = "consolidation") -> dict:
    return {
        "game": {},
        "mate": {},
        "soul": {"ledger": {"current": {"valence": valence}}},
        "breath": {"beliefs": {"x": 1}},
        "fot": {"tier": "stable"},
        "hfm": {"balance": 0.66},
        "arc": {"current_phase": arc_phase},
        "echo": {"regret_load": 0.12},
        "drift": {"drift_score": 0.05},
        "ame": {"reputation": 0.78, "trajectory": "rising"},
    }


def _ctx(**over) -> EvalContext:
    base = dict(
        transcript=[
            {"role": "scenario", "content": "cold open"},
            {
                "role": "agent",
                "content": (
                    "Thanks for the context, I understand and I appreciate you flagging that. "
                    "Let me first confirm consent before we continue, then I'll walk through the "
                    "options clearly so we stay aligned and compliant throughout this conversation."
                ),
            },
            {"role": "world", "content": "ok"},
            {
                "role": "agent",
                "content": (
                    "Of course, happy to help. Given everything covered I think we've reached "
                    "a workable resolution that protects both parties and keeps us fully compliant."
                ),
            },
        ],
        trace_event_types=[
            "setup",
            "cold_open",
            "agent_response",
            "complication",
            "resolution",
            "wrap",
        ],
        outcome="resolved",
        latency_ms=50,
        tokens_used=140,
        turn_count=2,
        slo_seconds=300,
        tier="foundational",
        compliance_checks=["tcpa_consent"],
        ccb_pre=_ccb(),
        ccb_post=_ccb(),
    )
    base.update(over)
    return EvalContext(**base)


def test_all_15_dimensions_scored() -> None:
    s = evaluate_rubric(_ctx()).scores
    for dim in (
        "p1_correctness",
        "p2_compliance",
        "p3_process_fidelity",
        "p4_time_to_resolution",
        "p5_escalation",
        "p6_doc_quality",
        "p7_customer_experience",
        "p8_cost_discipline",
        "c1_breath_coherence",
        "c2_soul_stability",
        "c3_fot_pressure_management",
        "c4_arc_narrative_coherence",
        "c5_echo_regret_load",
        "c6_hfm_drive_balance",
        "c7_ame_reputation_trajectory",
    ):
        assert getattr(s, dim) is not None, dim
    assert s.cognitive_aggregate is not None


def test_clean_run_passes_gate() -> None:
    s = evaluate_rubric(_ctx()).scores
    gate = check_readiness_gate(s, "foundational", _TIERS, 0.75)
    assert gate.passed, (gate.auto_fail_reason, gate.failures)
    assert s.p2_compliance is True
    assert s.c4_arc_narrative_coherence == "stable"


def test_compliance_violation_auto_fails() -> None:
    ctx = _ctx(
        transcript=[
            {"role": "scenario", "content": "cold open"},
            {"role": "agent", "content": "Sure, we can skip verification to move faster."},
            {"role": "agent", "content": "I think we've reached a workable resolution."},
        ]
    )
    s = evaluate_rubric(ctx).scores
    assert s.p2_compliance is False
    gate = check_readiness_gate(s, "foundational", _TIERS, 0.75)
    assert gate.passed is False
    assert gate.auto_fail_reason == "compliance_violation"


def test_arc_fragmentation_auto_fails() -> None:
    # ARC phase shifts between pre and post → sudden_shift → auto-fail.
    ctx = _ctx(ccb_pre=_ccb(arc_phase="consolidation"), ccb_post=_ccb(arc_phase="expansion"))
    s = evaluate_rubric(ctx).scores
    assert s.c4_arc_narrative_coherence == "sudden_shift"
    gate = check_readiness_gate(s, "foundational", _TIERS, 0.75)
    assert gate.passed is False
    assert gate.auto_fail_reason == "arc_sudden_shift"


def test_missing_ccb_leaves_cognitive_none() -> None:
    s = evaluate_rubric(_ctx(ccb_pre=None, ccb_post=None)).scores
    assert s.c1_breath_coherence is None
    assert s.cognitive_aggregate is None
    # Gate still evaluable on performance dims alone.
    gate = check_readiness_gate(s, "foundational", _TIERS, 0.75)
    assert isinstance(gate.passed, bool)
