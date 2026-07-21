"""Grafana dashboard-as-code — valid JSON that references real emitted metrics (ADR-0029)."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DASHBOARD = REPO_ROOT / "infra" / "grafana" / "dashboards" / "simforge-overview.json"

# Core metrics the overview dashboard must chart (guards against a metric rename).
_EXPECTED_METRICS = {
    "simforge_runs_total",
    "simforge_readiness_gate_total",
    "simforge_certs_issued_total",
    "simforge_gaps_open",
    "simforge_pdp_decisions_total",
    "simforge_pdp_decision_latency_seconds",
    "simforge_pdp_cache_hit_ratio",
    "simforge_eval_latency_seconds",
    "simforge_tokens_used_total",
}


def test_dashboard_is_valid_json_with_panels() -> None:
    dash = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    assert dash["uid"] == "simforge-overview"
    assert len(dash["panels"]) >= 8
    for p in dash["panels"]:
        assert p["title"] and p["targets"]
        assert all("expr" in t for t in p["targets"])


def test_dashboard_references_real_metrics() -> None:
    text = DASHBOARD.read_text(encoding="utf-8")
    missing = [m for m in _EXPECTED_METRICS if m not in text]
    assert not missing, f"dashboard omits metrics: {missing}"


def test_dashboard_metrics_are_actually_emitted() -> None:
    # The referenced metrics must exist in the API's metric registry — catch a rename in CI.
    from prometheus_client import REGISTRY

    import src.telemetry.metrics as m  # noqa: F401  (registers collectors on import)

    registered = {mf.name for mf in REGISTRY.collect()}
    # Counters expose as <name>_total; the family name drops the _total. Normalize both ways.
    known = registered | {n + "_total" for n in registered}
    for metric in _EXPECTED_METRICS:
        base = metric[: -len("_total")] if metric.endswith("_total") else metric
        assert metric in known or base in registered, f"{metric} not emitted"
