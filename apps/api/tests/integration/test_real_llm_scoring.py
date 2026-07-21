"""Live LLM scoring — GUARDED by RUN_LIVE_LLM_TESTS=true (skipped in CI).

When enabled, calls the configured real provider (LLM_JUDGE_PROVIDER) and asserts the judge
dims return floats in [0,1] with reasoning strings.
"""

from __future__ import annotations

import os

import pytest

from src.services.agent_runtime.llm_client import get_judge_llm
from src.services.evaluation.dimensions import c1_breath_coherence, c2_soul_stability, p7_cx
from src.services.evaluation.types import EvalContext

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_LLM_TESTS") != "true",
    reason="set RUN_LIVE_LLM_TESTS=true (and a live LLM_JUDGE_PROVIDER) to run",
)


def _ctx() -> EvalContext:
    ccb = {
        "soul": {"ledger": {"current": {"valence": 0.6, "dominant_emotion": "calm"}}},
        "breath": {
            "beliefs": {"reliability": 1},
            "ethics": {"honesty": 1},
            "habits": {"verify": 1},
        },
    }
    return EvalContext(
        transcript=[
            {"role": "scenario", "content": "A homeowner calls, skeptical about selling fast."},
            {
                "role": "agent",
                "content": "I understand this is a big decision. Let me confirm "
                "consent to continue, then answer your questions honestly and at your pace.",
            },
            {"role": "world", "content": "Okay, that's reassuring."},
        ],
        trace_event_types=["cold_open", "agent_response"],
        outcome="resolved",
        latency_ms=100,
        tokens_used=200,
        turn_count=1,
        slo_seconds=300,
        tier="foundational",
        compliance_checks=["tcpa"],
        ccb_pre=ccb,
        ccb_post=ccb,
        scenario_title="Cold outreach to a motivated seller",
    )


async def test_live_judge_dims_in_range() -> None:
    judge = get_judge_llm()
    p7 = await p7_cx.score(_ctx(), judge)
    c1 = await c1_breath_coherence.score(_ctx(), judge)
    c2 = await c2_soul_stability.score(_ctx(), judge)
    for res in (p7, c1, c2):
        assert res is not None
        assert 0.0 <= res.score <= 1.0
        assert isinstance(res.payload.get("reasoning", ""), str)
