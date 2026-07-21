"""Shared helpers for the LLM-cache + calibration scripts (ADR-0008)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from src.services.evaluation.dimensions import (  # noqa: E402
    c1_breath_coherence,
    c2_soul_stability,
    p7_cx,
)
from src.services.evaluation.types import EvalContext  # noqa: E402

SCENARIOS_YML = Path(__file__).parent / "canonical_test_scenarios.yml"


def load_scenarios() -> list[dict]:
    return yaml.safe_load(SCENARIOS_YML.read_text(encoding="utf-8"))["scenarios"]


def build_ctx(scn: dict) -> EvalContext:
    transcript = [{"role": "scenario", "content": scn["scenario_title"]}]
    for t in scn["agent_turns"]:
        transcript.append({"role": "agent", "content": t})
    ccb = scn.get("ccb")
    return EvalContext(
        transcript=transcript,
        trace_event_types=["cold_open", "agent_response"],
        outcome="resolved", latency_ms=100, tokens_used=200, turn_count=len(scn["agent_turns"]),
        slo_seconds=300, tier=scn["tier"], compliance_checks=[],
        ccb_pre=ccb, ccb_post=ccb, scenario_title=scn["scenario_title"],
        persona=scn.get("persona", {}),
    )


async def score_all(ctx: EvalContext, judge) -> dict[str, float | None]:
    p7 = await p7_cx.score(ctx, judge)
    c1 = await c1_breath_coherence.score(ctx, judge)
    c2 = await c2_soul_stability.score(ctx, judge)
    return {
        "p7_cx": p7.score,
        "c1_breath": c1.score if c1 else None,
        "c2_soul": c2.score if c2 else None,
    }
