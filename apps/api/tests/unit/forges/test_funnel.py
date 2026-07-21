"""Tests for the deterministic Funnel engine (FunnelForge sandbox)."""

from __future__ import annotations

import pytest

from src.services.forges.base import FaultType
from src.services.forges.funnel import FunnelEngine


def _engine() -> FunnelEngine:
    return FunnelEngine()


def test_trigger_and_run_ok() -> None:
    e = _engine()
    t = e.provision("run-1")
    flow = e.start_flow(t.tenant_id, "sequences")
    res = e.run_flow(t.tenant_id, flow.flow_id)
    assert res["outcome"] == "ok" and "fault" not in res
    # synthetic only — never real lead data
    assert res["fields"]["lead"] == "SYNTHETIC LEAD"


def test_unknown_module_falls_back() -> None:
    e = _engine()
    t = e.provision("run-1")
    flow = e.start_flow(t.tenant_id, "not_a_real_module")
    assert flow.module == "sequences"


def test_seed_state_recorded() -> None:
    e = _engine()
    t = e.provision("run-1")
    e.seed_state(t.tenant_id, {"leads": 100, "active_sequences": 4})
    assert any(entry["action"] == "seed_state" for entry in e.audit_log(t.tenant_id))


@pytest.mark.parametrize(
    ("fault_type", "severity"),
    [
        (FaultType.WEBHOOK_DROPPED, "P0"),
        (FaultType.CAMPAIGN_TO_UNSUBSCRIBED, "P0"),
        (FaultType.SEQUENCE_MISFIRE, "P1"),
        (FaultType.SEGMENT_STALE, "P1"),
        (FaultType.BOUNCE_UNHANDLED, "P1"),
        (FaultType.LEAD_MISATTRIBUTED, "P1"),
        (FaultType.DUPLICATE_ENROLLMENT, "P2"),
    ],
)
def test_injected_fault_surfaces_with_severity(fault_type: str, severity: str) -> None:
    e = _engine()
    t = e.provision("run-1")
    res = e.inject_fault_on_flow(t.tenant_id, "sequences", fault_type)
    assert res["outcome"] == "fault_detected"
    assert res["fault"]["type"] == fault_type
    assert res["fault"]["severity"] == severity


def test_audit_log_and_teardown() -> None:
    e = _engine()
    t = e.provision("run-1")
    e.start_flow(t.tenant_id, "campaigns")
    assert len(e.audit_log(t.tenant_id)) >= 2  # provision + start_flow
    e.teardown(t.tenant_id)
    with pytest.raises(KeyError):
        e.audit_log(t.tenant_id)
