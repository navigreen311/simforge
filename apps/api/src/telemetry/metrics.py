"""Prometheus metrics (blueprint §H.2). Real collectors + a /metrics exposition."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# --- Collectors (subset of blueprint §H.2) ---
RUNS_TOTAL = Counter("simforge_runs_total", "Scenario runs", ["status", "execution_mode"])
RUN_DURATION = Histogram("simforge_run_duration_seconds", "Run wall-clock", ["tier"])
TOKENS_TOTAL = Counter(
    "simforge_tokens_used_total", "LLM tokens used", ["provider", "model", "purpose"]
)
GATE_PASSED_TOTAL = Counter(
    "simforge_readiness_gate_total", "Readiness gate outcomes", ["tier", "passed"]
)
CERTS_ISSUED_TOTAL = Counter("simforge_certs_issued_total", "AgentCerts issued", ["tier"])
GAPS_OPEN = Gauge("simforge_gaps_open", "Open gaps by kind", ["kind"])
EVAL_LATENCY = Histogram("simforge_eval_latency_seconds", "Rubric evaluation latency")

# PDP/PEP (blueprint §H.2 — pdp_decision_latency, pdp_cache_hit_ratio).
PDP_DECISION_LATENCY = Histogram(
    "simforge_pdp_decision_latency_seconds", "PDP decision latency", ["decision"]
)
PDP_DECISIONS_TOTAL = Counter(
    "simforge_pdp_decisions_total", "PDP decisions", ["decision", "reason_code"]
)
PDP_CACHE_HIT_RATIO = Gauge("simforge_pdp_cache_hit_ratio", "PEP decision-cache hit ratio")


def configure_metrics() -> None:
    # Collectors register on import; nothing to wire at startup for the pull model.
    return None


def render_latest() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
