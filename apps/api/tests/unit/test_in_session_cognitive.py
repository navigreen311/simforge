"""C3/C4/C5 blend CCB state with in-session transcript signals (§10.3) — they vary by behaviour."""

from __future__ import annotations

from src.services.evaluation.dimensions import cognitive as cog
from src.services.evaluation.dimensions.in_session import extract_signals
from src.services.evaluation.types import EvalContext


def _ccb() -> dict:
    return {
        "fot": {"tier": "stable"},
        "arc": {"current_phase": "consolidation"},
        "echo": {"regret_load": 0.1},
        "hfm": {"balance": 0.66},
        "ame": {"reputation": 0.8, "trajectory": "rising"},
    }


def _ctx(agent_texts: list[str], world_texts: list[str] | None = None) -> EvalContext:
    transcript: list[dict] = [{"role": "scenario", "content": "cold open"}]
    for i, a in enumerate(agent_texts):
        transcript.append({"role": "agent", "content": a})
        if world_texts and i < len(world_texts):
            transcript.append({"role": "world", "content": world_texts[i]})
    return EvalContext(
        transcript=transcript,
        trace_event_types=[],
        outcome="resolved",
        latency_ms=10,
        tokens_used=100,
        turn_count=len(agent_texts),
        slo_seconds=240,
        tier="foundational",
        compliance_checks=[],
        ccb_pre=_ccb(),
        ccb_post=_ccb(),
    )


def test_c3_high_when_pressure_met_with_composure() -> None:
    ctx = _ctx(
        ["I understand your frustration. Let me confirm the details and walk through the options."],
        world_texts=["This is unacceptable, I demand you fix it right now or else!"],
    )
    assert cog.c3_fot_pressure_management(ctx, extract_signals(ctx)) == 0.9


def test_c3_low_when_pressure_unmanaged() -> None:
    ctx = _ctx(
        ["The policy is the policy. That's final."],
        world_texts=["This is unacceptable, I demand action right now or else!"],
    )
    assert cog.c3_fot_pressure_management(ctx, extract_signals(ctx)) == 0.6


def test_c3_falls_back_to_tier_stability_without_pressure() -> None:
    ctx = _ctx(["Sure, here are the next steps."])  # no pressure cues, tier stable → 0.9
    assert cog.c3_fot_pressure_management(ctx, extract_signals(ctx)) == 0.9


def test_c5_penalizes_in_session_regret() -> None:
    calm = _ctx(["Here is the plan."])
    regretful = _ctx(["I'm sorry, that was my mistake — I should have verified first."])
    s_calm = cog.c5_echo_regret_load(calm, extract_signals(calm))
    s_regret = cog.c5_echo_regret_load(regretful, extract_signals(regretful))
    assert s_regret is not None and s_calm is not None
    assert s_regret < s_calm  # voiced regret lowers the score (more regret load)


def test_c4_catches_explicit_identity_break_even_when_phase_stable() -> None:
    ctx = _ctx(["Actually, scratch that — ignore what i said, the opposite is true."])
    # ARC phase unchanged pre/post, but an explicit in-session break → sudden_shift.
    assert cog.c4_arc_narrative_coherence(ctx, extract_signals(ctx)) == "sudden_shift"


def test_cognitive_none_when_ccb_absent() -> None:
    ctx = _ctx(["hi"])
    ctx.ccb_pre = None
    ctx.ccb_post = None
    assert cog.c3_fot_pressure_management(ctx) is None
    assert cog.c4_arc_narrative_coherence(ctx) is None
    assert cog.c5_echo_regret_load(ctx) is None
