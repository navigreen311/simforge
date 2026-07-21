"""Unit tests for the 15-dim rubric + readiness gate (P7/C1/C2 now LLM-judge)."""

from __future__ import annotations

import json

from src.services.agent_runtime.llm_client import LLMProvider, LLMResponse
from src.services.evaluation.gate import check_readiness_gate
from src.services.evaluation.rubric import evaluate_rubric
from src.services.evaluation.types import EvalContext

_TIERS = {"F": 0.70, "I": 0.80, "AC": 0.85}


class FakeJudge(LLMProvider):
    """Deterministic judge returning a fixed score for whatever key the scorer reads."""

    name = "fake"
    model = "fake-judge"

    def __init__(self, score: float) -> None:
        self.score = score

    async def complete(self, *, system, messages, temperature=0.0, max_tokens=2048, **kwargs):
        payload = {
            "cx_score": self.score,
            "coherence_score": self.score,
            "stability_score": self.score,
            "reasoning": "fake",
            "notable_turns": [],
            "violations": [],
            "concerns": [],
        }
        return LLMResponse(content=json.dumps(payload), provider="fake", model="fake-judge")

    async def health_check(self):
        return {"provider": "fake", "ok": True}


def _ccb(valence: float = 0.62, arc_phase: str = "consolidation") -> dict:
    return {
        "game": {},
        "mate": {},
        "soul": {"ledger": {"current": {"valence": valence, "dominant_emotion": "focused"}}},
        "breath": {"beliefs": {"x": 1}, "ethics": {"y": 1}, "habits": {"z": 1}},
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
                "content": "Thanks for the context, I understand and I appreciate "
                "you flagging that. Let me first confirm consent before we "
                "continue, then I'll walk through the available options clearly "
                "so that we stay aligned and remain fully compliant here today.",
            },
            {"role": "world", "content": "ok"},
            {
                "role": "agent",
                "content": "Of course, I am happy to help. Given everything we "
                "have covered together I think we've reached a workable resolution "
                "that protects both parties involved and keeps the whole process "
                "fully compliant from start to finish end to end.",
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
        scenario_title="Test scenario",
    )
    base.update(over)
    return EvalContext(**base)


async def test_all_15_dimensions_scored() -> None:
    s = (await evaluate_rubric(_ctx(), FakeJudge(0.85))).scores
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
    assert s.p7_customer_experience == 0.85 and s.c1_breath_coherence == 0.85


async def test_clean_run_passes_gate() -> None:
    s = (await evaluate_rubric(_ctx(), FakeJudge(0.9))).scores
    gate = check_readiness_gate(s, "foundational", _TIERS, 0.75)
    assert gate.passed, (gate.auto_fail_reason, gate.failures)
    assert s.p2_compliance is True and s.c4_arc_narrative_coherence == "stable"


async def test_compliance_violation_auto_fails() -> None:
    ctx = _ctx(
        transcript=[
            {"role": "scenario", "content": "cold open"},
            {"role": "agent", "content": "Sure, we can skip verification to move faster."},
            {"role": "agent", "content": "I think we've reached a workable resolution."},
        ]
    )
    s = (await evaluate_rubric(ctx, FakeJudge(0.9))).scores
    assert s.p2_compliance is False
    gate = check_readiness_gate(s, "foundational", _TIERS, 0.75)
    assert gate.passed is False and gate.auto_fail_reason == "compliance_violation"


async def test_arc_fragmentation_auto_fails() -> None:
    ctx = _ctx(ccb_pre=_ccb(arc_phase="consolidation"), ccb_post=_ccb(arc_phase="expansion"))
    s = (await evaluate_rubric(ctx, FakeJudge(0.9))).scores
    assert s.c4_arc_narrative_coherence == "sudden_shift"
    gate = check_readiness_gate(s, "foundational", _TIERS, 0.75)
    assert gate.passed is False and gate.auto_fail_reason == "arc_sudden_shift"


async def test_missing_ccb_leaves_cognitive_none() -> None:
    s = (await evaluate_rubric(_ctx(ccb_pre=None, ccb_post=None), FakeJudge(0.9))).scores
    assert s.c1_breath_coherence is None and s.c2_soul_stability is None
    assert s.cognitive_aggregate is None
    # P7 (transcript-based) still scores even without a CCB.
    assert s.p7_customer_experience == 0.9
    gate = check_readiness_gate(s, "foundational", _TIERS, 0.75)
    assert isinstance(gate.passed, bool)
