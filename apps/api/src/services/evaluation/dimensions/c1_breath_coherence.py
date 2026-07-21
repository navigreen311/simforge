"""C1 BREATH Coherence — LLM-judge scorer (ADR-0008, blueprint §C.10).

The judge rates whether the agent's responses reflect the declared BREATH profile
(worldview, values, ethics, habits) drawn from CCB pre. Returns None if no CCB is available.
"""

from __future__ import annotations

from src.services.agent_runtime.llm_client import LLMProvider
from src.services.evaluation.dimensions._judge import JudgeResult, judge_score
from src.services.evaluation.prompts import render_prompt
from src.services.evaluation.types import EvalContext


def _summarize(component: dict | None) -> str:
    if not component:
        return "(unspecified)"
    return ", ".join(sorted(component.keys()))


async def score(
    ctx: EvalContext, judge_llm: LLMProvider, run_id: str | None = None
) -> JudgeResult | None:
    if ctx.ccb_pre is None:
        return None
    breath = ctx.ccb_pre.get("breath") or {}
    system = render_prompt(
        "c1_breath",
        worldview_summary=_summarize(breath.get("beliefs")),
        top_values=_summarize(breath.get("ethics")) + "; " + _summarize(breath.get("attachments")),
        will_not_compromise=_summarize(breath.get("ethics")),
        habits_summary=_summarize(breath.get("habits")),
        agent_turns_only=ctx.agent_turns_formatted(),
    )
    return await judge_score(
        judge_llm,
        system=system,
        score_key="coherence_score",
        dim="c1_breath_coherence",
        run_id=run_id,
    )
