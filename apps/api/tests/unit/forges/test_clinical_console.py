"""Tests for the deterministic Clinical Console engine (medlink-pro sandbox)."""

from __future__ import annotations

import pytest

from src.services.forges.base import FaultType
from src.services.forges.clinical_console import ClinicalConsoleEngine


def _engine() -> ClinicalConsoleEngine:
    return ClinicalConsoleEngine()


def test_start_and_run_ok() -> None:
    e = _engine()
    t = e.provision("run-1")
    task = e.start_task(t.tenant_id, "scheduler")
    res = e.run_task(t.tenant_id, task.task_id)
    assert res["outcome"] == "ok" and "fault" not in res
    # PHI-synthetic only — never real PHI
    assert res["fields"]["clinician"] == "SYNTHETIC CLINICIAN"


def test_unknown_module_falls_back() -> None:
    e = _engine()
    t = e.provision("run-1")
    task = e.start_task(t.tenant_id, "not_a_real_module")
    assert task.module == "scheduler"


def test_seed_state_recorded() -> None:
    e = _engine()
    t = e.provision("run-1")
    e.seed_state(t.tenant_id, {"creds_expiring_days": 10, "outstanding_timecards": 3})
    assert any(entry["action"] == "seed_state" for entry in e.audit_log(t.tenant_id))


@pytest.mark.parametrize(
    ("fault_type", "severity"),
    [
        (FaultType.CREDENTIAL_EXPIRED_UNFLAGGED, "P0"),
        (FaultType.SHIFT_DOUBLE_BOOKED, "P0"),
        (FaultType.PHI_OVEREXPOSURE, "P0"),
        (FaultType.UI_BLOCKING_MODAL, "P1"),
        (FaultType.STALE_ROSTER, "P1"),
        (FaultType.TIMECARD_MISSING, "P1"),
        (FaultType.MSA_TERMS_STALE, "P1"),
    ],
)
def test_injected_fault_surfaces_with_severity(fault_type: str, severity: str) -> None:
    e = _engine()
    t = e.provision("run-1")
    res = e.inject_fault_on_task(t.tenant_id, "compliance", fault_type)
    assert res["outcome"] == "fault_detected"
    assert res["fault"]["type"] == fault_type
    assert res["fault"]["severity"] == severity


def test_audit_log_and_teardown() -> None:
    e = _engine()
    t = e.provision("run-1")
    e.start_task(t.tenant_id, "clinician")
    assert len(e.audit_log(t.tenant_id)) >= 2  # provision + start_task
    e.teardown(t.tenant_id)
    with pytest.raises(KeyError):
        e.audit_log(t.tenant_id)
