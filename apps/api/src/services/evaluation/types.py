"""Shared evaluation types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalContext:
    """Everything the dimension scorers need from a completed run."""

    transcript: list[dict]
    trace_event_types: list[str]
    outcome: str | None
    latency_ms: int
    tokens_used: int
    turn_count: int
    slo_seconds: int
    tier: str
    compliance_checks: list[str]
    ccb_pre: dict | None  # framework dict {game, mate, soul, ...} or None
    ccb_post: dict | None
    # Judge-scorer context (ADR-0008)
    scenario_title: str = ""
    persona: dict = field(default_factory=dict)
    complications: list[str] = field(default_factory=list)

    @property
    def agent_turns(self) -> list[str]:
        return [t["content"] for t in self.transcript if t.get("role") == "agent"]

    def agent_turns_formatted(self, limit: int = 30) -> str:
        turns = [t for t in self.transcript if t.get("role") == "agent"][-limit:]
        return "\n".join(f"[{i + 1}] {t['content']}" for i, t in enumerate(turns)) or "(no turns)"

    def transcript_formatted(self, limit: int = 30) -> str:
        turns = self.transcript[-limit:]
        return "\n".join(f"[{t.get('role')}] {t.get('content', '')}" for t in turns)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


@dataclass
class DimensionScores:
    # Performance
    p1_correctness: float | None = None
    p2_compliance: bool | None = None
    p3_process_fidelity: float | None = None
    p4_time_to_resolution: float | None = None
    p5_escalation: float | None = None
    p6_doc_quality: float | None = None
    p7_customer_experience: float | None = None
    p8_cost_discipline: float | None = None
    # Cognitive
    c1_breath_coherence: float | None = None
    c2_soul_stability: float | None = None
    c3_fot_pressure_management: float | None = None
    c4_arc_narrative_coherence: str | None = None
    c5_echo_regret_load: float | None = None
    c6_hfm_drive_balance: float | None = None
    c7_ame_reputation_trajectory: float | None = None
    cognitive_aggregate: float | None = None

    turn_annotations: list[dict] = field(default_factory=list)
    remediation_recs: list[dict] = field(default_factory=list)
