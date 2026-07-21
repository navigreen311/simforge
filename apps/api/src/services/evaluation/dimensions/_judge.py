"""Shared LLM-judge invocation: call → parse JSON → one retry → heuristic fallback (ADR-0008)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from src.services.agent_runtime.llm_client import LLMProvider
from src.telemetry.logging import get_logger

log = get_logger("judge")

_FALLBACK_SCORE = 0.5


@dataclass
class JudgeResult:
    score: float
    payload: dict
    fell_back: bool = False


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    # Tolerate models that wrap JSON in prose/code fences.
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


async def judge_score(
    judge_llm: LLMProvider,
    *,
    system: str,
    score_key: str,
    dim: str,
    run_id: str | None = None,
) -> JudgeResult:
    """Run a judge prompt (temperature=0), parse `score_key`, retry once, else fall back."""
    messages = [{"role": "world", "content": "Evaluate now."}]
    resp = await judge_llm.complete(
        system=system,
        messages=messages,
        temperature=0.0,
        max_tokens=512,
        purpose="judge",
        run_id=run_id,
    )
    parsed = _extract_json(resp.content)
    if parsed is None or score_key not in parsed:
        retry_system = system + "\n\nRespond ONLY with valid JSON. Previous response was invalid."
        resp = await judge_llm.complete(
            system=retry_system,
            messages=messages,
            temperature=0.0,
            max_tokens=512,
            purpose="judge",
            run_id=run_id,
        )
        parsed = _extract_json(resp.content)

    if parsed is None or score_key not in parsed:
        log.warning("judge_fallback", dim=dim, run_id=run_id)
        return JudgeResult(score=_FALLBACK_SCORE, payload={}, fell_back=True)

    try:
        score = max(0.0, min(1.0, float(parsed[score_key])))
    except (TypeError, ValueError):
        return JudgeResult(score=_FALLBACK_SCORE, payload=parsed, fell_back=True)
    return JudgeResult(score=score, payload=parsed)
