"""Venture enrichment from a spec document (Part B, Pass 1) — a PROPOSAL, never auto-applied.

Reuses the Scenario-Bank extraction pipeline (the same LLM client + JSON parser); this is a second
PROMPT, not a second extractor. It proposes refined venture metadata from the spec text for a human
to review as a diff. No fabrication: it must ground claims in the source, map compliance flags to
the existing Jurisdiction vocabulary, and output valid JSON only.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.services.agent_runtime.llm_client import get_agent_llm
from src.services.scenario_bank.extraction import _MAX_SOURCE_CHARS, _extract_json


@dataclass
class EnrichmentResult:
    ok: bool
    proposal: dict | None = None
    error: str | None = None


def _build_system(allowed_flags: list[str]) -> str:
    return f"""You read a VENTURE SPEC and propose refined metadata for that venture.

Rules:
- Do NOT invent capabilities, flags, or facts not supported by the SPEC TEXT. If the spec does not
  mention something, leave that field empty ([] or "").
- compliance_flags: choose ONLY from this exact list (drop anything not in it):
  {allowed_flags}
- internal_forges: names of internal platforms/Forges the venture runs on, if the spec names any.
- capabilities: Forge-capability ids the venture should certify against, if the spec implies any
  (short lowercase dotted ids, e.g. "medlink-pro.compliance.audit_response"); else [].
- Output ONLY this JSON (no prose, no code fences):
  {{"confidence": <0..1>,
    "description": "<one-paragraph plain-language description grounded in the spec, or ''>",
    "compliance_flags": ["<flag>", ...],
    "internal_forges": ["<name>", ...],
    "capabilities": ["<cap id>", ...]}}
- Set confidence < 0.5 if the spec is thin. Output valid JSON only."""


async def extract_venture_enrichment(text: str, allowed_flags: list[str]) -> EnrichmentResult:
    """Propose venture metadata from spec text. Returns a proposal (never applied) or an error."""
    body = (text or "").strip()
    if not body:
        return EnrichmentResult(ok=False, error="Spec text is empty — nothing to enrich from.")
    body = body[:_MAX_SOURCE_CHARS]

    provider = get_agent_llm()
    resp = await provider.complete(
        system=_build_system(allowed_flags),
        messages=[{"role": "world", "content": f"SPEC TEXT:\n{body}"}],
        temperature=0.0,
        max_tokens=800,
        purpose="enrichment",
    )
    parsed = _extract_json(resp.content)
    if parsed is None:
        return EnrichmentResult(
            ok=False,
            error="The model did not return valid JSON — no enrichment proposed. (In dev the stub "
            "provider cannot enrich; configure a real LLM provider.)",
        )

    allowed = set(allowed_flags)

    def _list(key: str) -> list[str]:
        v = parsed.get(key)
        return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []

    confidence = parsed.get("confidence")
    confidence = float(confidence) if isinstance(confidence, (int, float)) else None
    return EnrichmentResult(
        ok=True,
        proposal={
            "description": (parsed.get("description") or "").strip(),
            # map to the existing flag vocabulary; drop anything unknown (no fabrication)
            "complianceFlags": [f for f in _list("compliance_flags") if f in allowed],
            "internalForges": _list("internal_forges"),
            "capabilities": _list("capabilities"),
            "confidence": confidence,
        },
    )
