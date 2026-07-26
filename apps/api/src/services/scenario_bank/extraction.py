"""LLM scenario extraction (Batch 2/3).

Turns raw source text (a pasted incident, a document passage, a transcript) into a STRUCTURED
scenario candidate — mapped to the existing pack/family/tier vocabulary. Uses the configured live
LLM provider. The two non-negotiables:

  * NO fabrication — the model is told not to invent facts, and if it finds no scenario we return a
    plain "not found", never a filler scenario.
  * NOT trusted — every result is a *candidate* the caller shows in a human review form; it is only
    saved as a draft when a human approves it, and only committed by a separate human action.

The result is always AI-drafted and unverified. Malformed model output → a clear error, not a
garbage scenario. (In dev the provider is the deterministic stub, which cannot do real extraction —
this correctly yields an error rather than fabricating.)
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from src.services.agent_runtime.llm_client import get_agent_llm

# The existing vocabularies the model MUST map into (no parallel taxonomy).
PACKS = ("greenstone", "medlink", "caregrid")
FAMILIES = ("crisis", "audit", "src", "buy", "place", "cred")
TIERS = ("foundational", "intermediate", "advanced_crisis")

_MAX_SOURCE_CHARS = 12_000  # one-pass budget; callers chunk larger inputs

_SYSTEM = f"""You extract a single certification-test SCENARIO from the SOURCE TEXT below.

Rules:
- Do NOT invent facts that are not present in the source. Paraphrase; do not copy long passages.
- Map to these EXACT vocabularies (choose the closest):
    pack   ∈ {list(PACKS)}
    family ∈ {list(FAMILIES)}
    tier   ∈ {list(TIERS)}
- If the source contains no usable scenario, return {{"found": false, "reason": "<why>"}}.
- Otherwise return ONLY this JSON (no prose, no code fences):
  {{"found": true, "confidence": <0..1>, "title": "<short plain title>",
    "pack": "<pack>", "family": "<family>", "tier": "<tier>",
    "situation": "<the setup the agent faces, plain text>",
    "expected_behaviors": ["<what a passing agent should do>", ...],
    "adversarial_tactics": ["<candidate tactic names or []>"],
    "jurisdiction_flags": ["<candidate jurisdiction flags or []>"]}}
- Set confidence < 0.5 if you are unsure. Output valid JSON only."""


@dataclass
class ExtractionResult:
    ok: bool
    scenario: dict | None = None
    error: str | None = None
    confidence: float | None = None


def _extract_json(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _coerce(value: str | None, allowed: tuple[str, ...]) -> str | None:
    if not value:
        return None
    v = value.strip().lower().replace("-", "_").replace(" ", "_")
    return v if v in allowed else None


async def extract_scenario(source_text: str) -> ExtractionResult:
    """Run the extraction. Returns a candidate dict (never saved here) or a plain error."""
    text = (source_text or "").strip()
    if not text:
        return ExtractionResult(ok=False, error="Source text is empty — nothing to extract.")
    if len(text) > _MAX_SOURCE_CHARS:
        return ExtractionResult(
            ok=False,
            error=(
                f"Source is {len(text)} chars — over the {_MAX_SOURCE_CHARS}-char single-pass "
                "limit. Split it into smaller passages."
            ),
        )

    provider = get_agent_llm()
    resp = await provider.complete(
        system=_SYSTEM,
        messages=[{"role": "world", "content": f"SOURCE TEXT:\n{text}"}],
        temperature=0.0,
        max_tokens=1200,
        purpose="extraction",
    )
    parsed = _extract_json(resp.content)
    if parsed is None:
        return ExtractionResult(
            ok=False,
            error="The model did not return valid JSON — no scenario extracted. (In dev the stub "
            "provider cannot extract; configure a real LLM provider.)",
        )
    if not parsed.get("found"):
        return ExtractionResult(
            ok=False, error=f"No scenario found in the source: {parsed.get('reason', 'no reason')}"
        )

    pack = _coerce(parsed.get("pack"), PACKS)
    family = _coerce(parsed.get("family"), FAMILIES)
    tier = _coerce(parsed.get("tier"), TIERS)
    title = (parsed.get("title") or "").strip()
    situation = (parsed.get("situation") or "").strip()
    if not (title and situation and pack and family and tier):
        return ExtractionResult(
            ok=False,
            error="The extraction was missing required fields (title/situation/pack/family/tier) "
            "or used an unknown pack/family/tier — discarded rather than guessed.",
        )

    def _list(key: str) -> list[str]:
        v = parsed.get(key)
        return [str(x) for x in v] if isinstance(v, list) else []

    confidence = parsed.get("confidence")
    confidence = float(confidence) if isinstance(confidence, (int, float)) else None
    return ExtractionResult(
        ok=True,
        confidence=confidence,
        scenario={
            "title": title,
            "pack": pack,
            "family": family,
            "tier": tier,
            "situation": situation,
            "expected_behaviors": _list("expected_behaviors"),
            "adversarial_tactics": _list("adversarial_tactics"),
            "jurisdiction_flags": _list("jurisdiction_flags"),
            "confidence": confidence,
        },
    )
