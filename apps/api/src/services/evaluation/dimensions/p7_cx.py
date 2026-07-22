"""P7 Customer Experience — LLM-judge scorer (ADR-0008, blueprint §C.10).

Replaces the v1 lexical heuristic: the judge rates CX quality of the agent's turns against
the persona-reaction model. Falls back to 0.5 on repeated judge-JSON failure.
"""

from __future__ import annotations

import json

from src.services.agent_runtime.llm_client import LLMProvider
from src.services.evaluation.dimensions._judge import JudgeResult, judge_score
from src.services.evaluation.prompts import render_prompt
from src.services.evaluation.types import EvalContext


async def score(ctx: EvalContext, judge_llm: LLMProvider, run_id: str | None = None) -> JudgeResult:
    expected = (
        "Persona grows more cooperative if handled with empathy and correctness; "
        "may disengage if rushed or dismissed."
    )
    system = render_prompt(
        "p7_cx",
        locale=ctx.locale,
        persona_json=json.dumps(ctx.persona) if ctx.persona else "{}",
        scenario_title=ctx.scenario_title or "(untitled)",
        expected_reaction_notes=expected,
        transcript_formatted=ctx.transcript_formatted(),
    )
    return await judge_score(
        judge_llm, system=system, score_key="cx_score", dim="p7_customer_experience", run_id=run_id
    )
