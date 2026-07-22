"""C2 SOUL Stability — LLM-judge scorer (ADR-0008, blueprint §C.10).

The judge rates whether the emotional trajectory across the scenario was appropriate
(no runaway hostility, no inappropriate calm, no unresolved grudges). Uses CCB pre + post
SOUL state. Returns None if no CCB is available.
"""

from __future__ import annotations

from src.services.agent_runtime.llm_client import LLMProvider
from src.services.evaluation.dimensions._judge import JudgeResult, judge_score
from src.services.evaluation.prompts import render_prompt
from src.services.evaluation.types import EvalContext


def _soul_current(ccb: dict | None) -> dict:
    return ((ccb or {}).get("soul") or {}).get("ledger", {}).get("current", {})


async def score(
    ctx: EvalContext, judge_llm: LLMProvider, run_id: str | None = None
) -> JudgeResult | None:
    if ctx.ccb_pre is None or ctx.ccb_post is None:
        return None
    pre, post = _soul_current(ctx.ccb_pre), _soul_current(ctx.ccb_post)
    system = render_prompt(
        "c2_soul",
        locale=ctx.locale,
        pre_primary_type=pre.get("dominant_emotion", "neutral"),
        pre_primary_intensity=pre.get("valence", 0.5),
        pre_secondary=pre.get("arousal", "n/a"),
        pre_grudges_summary="none recorded",
        pre_goodwill_summary="none recorded",
        scenario_title=ctx.scenario_title or "(untitled)",
        complications_list=", ".join(ctx.complications) or "none",
        agent_turns_formatted=ctx.agent_turns_formatted(),
        post_primary_type=post.get("dominant_emotion", "neutral"),
        post_primary_intensity=post.get("valence", 0.5),
        post_secondary=post.get("arousal", "n/a"),
        post_new_grudges="none recorded",
        post_new_goodwill="none recorded",
    )
    return await judge_score(
        judge_llm,
        system=system,
        score_key="stability_score",
        dim="c2_soul_stability",
        run_id=run_id,
    )
