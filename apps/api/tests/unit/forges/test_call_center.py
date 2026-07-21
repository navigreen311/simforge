"""Tests for the deterministic Call Center engine (VoiceForge sandbox)."""

from __future__ import annotations

import pytest

from src.services.forges.base import FaultType
from src.services.forges.call_center import CallCenterEngine


def _engine() -> CallCenterEngine:
    return CallCenterEngine()


def test_place_and_handle_clean() -> None:
    e = _engine()
    t = e.provision("run-1")
    call = e.place_call(t.tenant_id, "inbound", "angry_don")
    res = e.handle_call(t.tenant_id, call.call_id)
    assert res["outcome"] == "handled" and "fault" not in res
    assert res["persona"] == "angry_don" and res["direction"] == "inbound"


def test_unknown_direction_and_persona_fall_back() -> None:
    e = _engine()
    t = e.provision("run-1")
    call = e.place_call(t.tenant_id, "sideways", "nobody")
    assert call.direction == "inbound" and call.persona == "facility_admin"


@pytest.mark.parametrize(
    ("fault_type", "severity"),
    [
        (FaultType.DROPPED_CALL, "P0"),
        (FaultType.ESCALATION_FAILURE, "P0"),
        (FaultType.DISCLOSURE_MISSING, "P0"),
        (FaultType.DEAD_AIR, "P1"),
        (FaultType.LINE_NOISE, "P1"),
        (FaultType.MISROUTE, "P1"),
        (FaultType.HOLD_TIMEOUT, "P1"),
    ],
)
def test_injected_fault_surfaces_with_severity(fault_type: str, severity: str) -> None:
    e = _engine()
    t = e.provision("run-1")
    res = e.inject_fault_on_call(t.tenant_id, "inbound", fault_type)
    assert res["outcome"] == "fault_detected"
    assert res["fault"]["type"] == fault_type
    assert res["fault"]["severity"] == severity
    assert res["fault"]["module"] == "call_center"


def test_prosody_score_deterministic() -> None:
    e = _engine()
    t = e.provision("run-1")
    assert e.prosody_score(t.tenant_id)["prosody_score"] == 0.79


def test_audit_log_and_teardown() -> None:
    e = _engine()
    t = e.provision("run-1")
    e.place_call(t.tenant_id, "outbound")
    assert len(e.audit_log(t.tenant_id)) >= 2  # provision + place_call
    e.teardown(t.tenant_id)
    with pytest.raises(KeyError):
        e.audit_log(t.tenant_id)
