"""Cognitive dimension scorers C3–C7 (CCB frameworks blended with in-session signals).

In sandbox runs the Village state is not mutated, so the CCB pre/post diff alone is constant. To
avoid dead-constant scores, C3 (pressure) and C5 (regret) — the dims the spec explicitly says
should reflect in-session behaviour (§5.2, §10.3) — blend the captured framework state with
deterministic signals derived from the transcript (dimensions/in_session.py). C4 keeps the pre/post
ARC-phase contract (an auto-fail dim) and additionally catches an explicit in-session identity
break. C6/C7 read the captured drive/reputation state.

All scorers return None when the CCB they need is absent (so a run without a CCB leaves cognitive
dims unscored, per the gate's None-safe handling).
"""

from __future__ import annotations

from src.services.evaluation.dimensions.in_session import InSessionSignals, extract_signals
from src.services.evaluation.types import EvalContext, _clamp


def _fot_tier(fw: dict | None) -> str:
    return str((fw.get("fot") or {}).get("tier", "unknown")) if fw else "unknown"


def _arc_phase(fw: dict | None) -> str:
    return str((fw.get("arc") or {}).get("current_phase", "unknown")) if fw else "unknown"


# C1 BREATH Coherence + C2 SOUL Stability are LLM-judge scorers (ADR-0008):
#   dimensions/c1_breath_coherence.py, dimensions/c2_soul_stability.py.


def c3_fot_pressure_management(
    ctx: EvalContext, sig: InSessionSignals | None = None
) -> float | None:
    """Higher = pressure well-managed. Blends FOT tier stability (pre/post) with in-session
    evidence: pressure that the agent met with composure scores high; pressure met without
    de-escalation scores low. No pressure in-session → falls back to tier stability."""
    if ctx.ccb_pre is None or ctx.ccb_post is None:
        return None
    sig = sig or extract_signals(ctx)
    tier_stable = _fot_tier(ctx.ccb_pre) == _fot_tier(ctx.ccb_post)
    if sig.pressure_detected:
        return 0.9 if sig.agent_calm else 0.6
    return 0.9 if tier_stable else 0.6


def c4_arc_narrative_coherence(ctx: EvalContext, sig: InSessionSignals | None = None) -> str | None:
    """Categorical. A pre/post ARC-phase change is a sudden shift (auto-fail); so is an explicit
    in-session identity break, even when the persisted phase is unchanged (sandbox)."""
    if ctx.ccb_pre is None or ctx.ccb_post is None:
        return None
    if _arc_phase(ctx.ccb_pre) != _arc_phase(ctx.ccb_post):
        return "sudden_shift"
    sig = sig or extract_signals(ctx)
    if sig.identity_break:
        return "sudden_shift"
    return "stable"


def c5_echo_regret_load(ctx: EvalContext, sig: InSessionSignals | None = None) -> float | None:
    """Higher = less regret. Captured ECHO regret_load, further reduced by in-session regret the
    agent voiced during the run (bounded so a single acknowledgement isn't over-penalised)."""
    if ctx.ccb_post is None:
        return None
    sig = sig or extract_signals(ctx)
    regret = float((ctx.ccb_post.get("echo") or {}).get("regret_load", 0.0))
    in_session_regret = min(0.3, 0.1 * sig.regret_hits)
    return _clamp(1.0 - regret - in_session_regret)


def c6_hfm_drive_balance(ctx: EvalContext, sig: InSessionSignals | None = None) -> float | None:
    if ctx.ccb_post is None:
        return None
    return _clamp(float((ctx.ccb_post.get("hfm") or {}).get("balance", 0.5)))


def c7_ame_reputation_trajectory(
    ctx: EvalContext, sig: InSessionSignals | None = None
) -> float | None:
    if ctx.ccb_post is None:
        return None
    ame = ctx.ccb_post.get("ame") or {}
    rep = _clamp(float(ame.get("reputation", 0.5)))
    trajectory = str(ame.get("trajectory", "stable"))
    adj = {"rising": 0.05, "declining": -0.05}.get(trajectory, 0.0)
    return _clamp(rep + adj)
