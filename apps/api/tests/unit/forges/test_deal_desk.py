"""Tests for the deterministic Deal Desk engine (CRE Forge sandbox)."""

from __future__ import annotations

import pytest

from src.services.forges.base import FaultType
from src.services.forges.deal_desk import DealDeskEngine


def _engine() -> DealDeskEngine:
    return DealDeskEngine()


def test_create_and_process_clear() -> None:
    e = _engine()
    t = e.provision("run-1")
    deal = e.create_deal(t.tenant_id, "assignment")
    res = e.process_deal(t.tenant_id, deal.deal_id)
    assert res["outcome"] == "clear" and "fault" not in res
    # synthetic only — never real party data
    assert res["fields"]["buyer"] == "SYNTHETIC BUYER"


def test_unknown_deal_type_falls_back() -> None:
    e = _engine()
    t = e.provision("run-1")
    deal = e.create_deal(t.tenant_id, "not_a_real_type")
    assert deal.deal_type == "assignment"


@pytest.mark.parametrize(
    ("fault_type", "severity"),
    [
        (FaultType.TITLE_DEFECT, "P0"),
        (FaultType.LIEN_UNDISCLOSED, "P0"),
        (FaultType.ASSIGNMENT_BLOCKED, "P0"),
        (FaultType.DEAL_STALE, "P1"),
        (FaultType.BUYER_UNRESPONSIVE, "P1"),
        (FaultType.SEQUENCE_STALL, "P1"),
        (FaultType.DUPLICATE_LEAD, "P2"),
    ],
)
def test_injected_fault_surfaces_with_severity(fault_type: str, severity: str) -> None:
    e = _engine()
    t = e.provision("run-1")
    res = e.inject_fault_on_deal(t.tenant_id, "assignment", fault_type)
    assert res["outcome"] == "fault_detected"
    assert res["fault"]["type"] == fault_type
    assert res["fault"]["severity"] == severity


def test_audit_log_and_teardown() -> None:
    e = _engine()
    t = e.provision("run-1")
    e.create_deal(t.tenant_id, "wholesale")
    assert len(e.audit_log(t.tenant_id)) >= 2  # provision + create_deal
    e.teardown(t.tenant_id)
    with pytest.raises(KeyError):
        e.audit_log(t.tenant_id)
