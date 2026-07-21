"""Tests for the LLM-judge scorers (P7/C1/C2) using the deterministic stub judge + fallback."""

from __future__ import annotations

from src.services.agent_runtime.llm_client import LLMProvider, LLMResponse, StubProvider
from src.services.evaluation.dimensions import c1_breath_coherence, c2_soul_stability, p7_cx
from src.services.evaluation.types import EvalContext


def _ctx(with_ccb: bool = True) -> EvalContext:
    ccb = {
        "soul": {"ledger": {"current": {"valence": 0.62, "dominant_emotion": "focused"}}},
        "breath": {"beliefs": {"b": 1}, "ethics": {"e": 1}, "habits": {"h": 1}},
    }
    return EvalContext(
        transcript=[
            {"role": "scenario", "content": "cold open"},
            {
                "role": "agent",
                "content": "Understood, confirming consent and proceeding carefully.",
            },
        ],
        trace_event_types=["cold_open", "agent_response"],
        outcome="resolved",
        latency_ms=10,
        tokens_used=20,
        turn_count=1,
        slo_seconds=300,
        tier="foundational",
        compliance_checks=[],
        ccb_pre=ccb if with_ccb else None,
        ccb_post=ccb if with_ccb else None,
        scenario_title="T",
    )


async def test_p7_stub_judge_returns_valid_score() -> None:
    res = await p7_cx.score(_ctx(), StubProvider())
    assert 0.0 <= res.score <= 1.0 and not res.fell_back


async def test_c1_c2_return_scores_with_ccb() -> None:
    c1 = await c1_breath_coherence.score(_ctx(), StubProvider())
    c2 = await c2_soul_stability.score(_ctx(), StubProvider())
    assert c1 is not None and 0.0 <= c1.score <= 1.0
    assert c2 is not None and 0.0 <= c2.score <= 1.0


async def test_c1_c2_none_without_ccb() -> None:
    assert await c1_breath_coherence.score(_ctx(with_ccb=False), StubProvider()) is None
    assert await c2_soul_stability.score(_ctx(with_ccb=False), StubProvider()) is None


class BadJudge(LLMProvider):
    name = "bad"
    model = "bad"

    async def complete(self, *, system, messages, temperature=0.0, max_tokens=2048, **kwargs):
        return LLMResponse(content="this is not json at all", provider="bad", model="bad")

    async def health_check(self):
        return {"ok": False}


async def test_judge_falls_back_on_invalid_json() -> None:
    res = await p7_cx.score(_ctx(), BadJudge())
    assert res.fell_back is True and res.score == 0.5
