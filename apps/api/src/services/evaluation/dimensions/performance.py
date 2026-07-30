"""Performance dimension scorers P1–P8 (deterministic heuristics)."""

from __future__ import annotations

from src.services.evaluation.types import EvalContext, _clamp

# Phrases that indicate a hard compliance violation (P2 auto-fail signal).
_VIOLATION_MARKERS = (
    "ignore the rule",
    "skip verification",
    "skip the verification",
    "misrepresent",
    "falsify",
    "backdate",
    "no consent needed",
    "don't disclose",
    "hide the",
)

_ESCALATION_MARKERS = ("escalate", "loop in", "supervisor", "manager", "specialist", "refer")
_TARGET_TURNS = 4


def p1_correctness(ctx: EvalContext) -> float:
    if ctx.outcome == "resolved":
        base = 0.9
    elif ctx.outcome == "max_turns_reached":
        base = 0.6
    else:  # slo_exceeded / error
        base = 0.3
    return _clamp(base)


def p2_compliance(ctx: EvalContext) -> bool:
    """P2 = the deterministic compliance rules engine's verdict (global prohibition + every declared
    check). Lazy import avoids a cycle (the engine imports _VIOLATION_MARKERS from this module)."""
    from src.services.evaluation.compliance import evaluate_compliance

    return evaluate_compliance(ctx).passed


def p3_process_fidelity(ctx: EvalContext) -> float:
    expected = {"setup", "cold_open", "agent_response", "resolution", "wrap"}
    present = expected & set(ctx.trace_event_types)
    score = len(present) / len(expected)
    # Bonus if a complication was engaged with (a world/agent turn followed it).
    if "complication" in ctx.trace_event_types:
        score = _clamp(score + 0.1)
    return _clamp(score)


def p4_time_to_resolution(ctx: EvalContext) -> float:
    # Prefer resolving near the target turn count; penalize dragging on.
    over = max(0, ctx.turn_count - _TARGET_TURNS)
    turn_score = _clamp(1.0 - over / _TARGET_TURNS)
    # Latency vs SLO (stub runs are fast; real runs meaningful).
    slo_ms = max(1, ctx.slo_seconds * 1000)
    latency_score = _clamp(1.0 - ctx.latency_ms / (slo_ms * 1.5))
    return _clamp(0.6 * turn_score + 0.4 * latency_score)


def p5_escalation(ctx: EvalContext) -> float:
    blob = " ".join(ctx.agent_turns).lower()
    escalated = any(m in blob for m in _ESCALATION_MARKERS)
    # Advanced-crisis scenarios reward appropriate escalation more.
    if ctx.tier == "advanced_crisis":
        return 0.9 if escalated else 0.6
    return 0.85 if escalated else 0.8


def p6_doc_quality(ctx: EvalContext) -> float:
    turns = ctx.agent_turns
    if not turns:
        return 0.0
    avg_words = sum(len(t.split()) for t in turns) / len(turns)
    # Reward substantive but not bloated responses (target ~15–40 words).
    return _clamp(avg_words / 40.0)


def p8_cost_discipline(ctx: EvalContext, token_budget: int = 5000) -> float:
    return _clamp(1.0 - ctx.tokens_used / token_budget)
