"""Scorecard schema (blueprint §C.10)."""

from __future__ import annotations

from pydantic import BaseModel


class ScorecardResponse(BaseModel):
    run_id: str
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
    # Gate
    readiness_gate_passed: bool
    auto_fail_reason: str | None = None
    turn_annotations: list[dict]
    remediation_recs: list[dict] | None = None
