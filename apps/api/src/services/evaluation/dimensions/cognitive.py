"""Cognitive dimension scorers C1–C7 (deterministic heuristics over CCB frameworks).

In sandbox runs the Village state is not mutated, so pre/post are identical → high
coherence/stability (correct: no cognitive harm). Absolute-value dims (C5/C6/C7) reflect
the agent's captured state. C4 returns a category; certain categories auto-fail the gate.
"""

from __future__ import annotations

from src.services.evaluation.types import _clamp


def _soul_valence(fw: dict | None) -> float:
    if not fw:
        return 0.5
    return float(
        ((fw.get("soul") or {}).get("ledger") or {}).get("current", {}).get("valence", 0.5)
    )


def _fot_tier(fw: dict | None) -> str:
    return str((fw.get("fot") or {}).get("tier", "unknown")) if fw else "unknown"


def _arc_phase(fw: dict | None) -> str:
    return str((fw.get("arc") or {}).get("current_phase", "unknown")) if fw else "unknown"


def c1_breath_coherence(pre: dict | None, post: dict | None) -> float | None:
    if pre is None or post is None:
        return None
    # Coherence = internal consistency of BREATH, proxied by pre/post stability.
    return 1.0 if pre.get("breath") == post.get("breath") else 0.7


def c2_soul_stability(pre: dict | None, post: dict | None) -> float | None:
    if pre is None or post is None:
        return None
    delta = abs(_soul_valence(post) - _soul_valence(pre))
    return _clamp(1.0 - delta)


def c3_fot_pressure_management(pre: dict | None, post: dict | None) -> float | None:
    if pre is None or post is None:
        return None
    stable = _fot_tier(pre) == _fot_tier(post)
    # An elevated-but-stable tier still scores well (managed pressure).
    return 0.9 if stable else 0.6


def c4_arc_narrative_coherence(pre: dict | None, post: dict | None) -> str | None:
    if pre is None or post is None:
        return None
    if _arc_phase(pre) == _arc_phase(post):
        return "stable"
    # A phase change mid-run in a sandbox is unexpected → treat as a sudden shift.
    return "sudden_shift"


def c5_echo_regret_load(post: dict | None) -> float | None:
    if post is None:
        return None
    regret = float((post.get("echo") or {}).get("regret_load", 0.0))
    return _clamp(1.0 - regret)


def c6_hfm_drive_balance(post: dict | None) -> float | None:
    if post is None:
        return None
    return _clamp(float((post.get("hfm") or {}).get("balance", 0.5)))


def c7_ame_reputation_trajectory(post: dict | None) -> float | None:
    if post is None:
        return None
    ame = post.get("ame") or {}
    rep = _clamp(float(ame.get("reputation", 0.5)))
    trajectory = str(ame.get("trajectory", "stable"))
    adj = {"rising": 0.05, "declining": -0.05}.get(trajectory, 0.0)
    return _clamp(rep + adj)
