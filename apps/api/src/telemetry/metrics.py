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


def configure_metrics() -> None:
    # Collectors register on import; nothing to wire at startup for the pull model.
    return None


def render_latest() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
