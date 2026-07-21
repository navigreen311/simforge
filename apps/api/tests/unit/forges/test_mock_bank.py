"""Tests for the deterministic Mock Bank engine."""

from __future__ import annotations

import pytest

from src.services.forges.base import Fault, FaultType
from src.services.forges.mock_bank import MockBankEngine


def _engine() -> MockBankEngine:
    return MockBankEngine()


def test_provision_and_apply_approved() -> None:
    e = _engine()
    t = e.provision("run-1")
    res = e.apply(t.tenant_id, 200_000.0)
    assert res["outcome"] == "approved" and res["reference"].startswith("cf_app")
    assert "fault" not in res


def test_apply_declined_on_fault() -> None:
    e = _engine()
    t = e.provision("run-1")
    e.inject_fault(t.tenant_id, Fault(FaultType.DECLINATION, "P1", "declined", "bank"))
    res = e.apply(t.tenant_id, 200_000.0)
    assert res["outcome"] == "declined" and res["reason"] == "declination"
    assert res["fault"]["severity"] == "P1"


def test_wire_nsf_and_balance() -> None:
    e = _engine()
    t = e.provision("run-1")
    # over-balance wire fails with nsf
    big = e.wire(t.tenant_id, 10_000_000.0)
    assert big["outcome"] == "failed" and big["reason"] == "nsf"
    # a valid wire debits the balance
    ok = e.wire(t.tenant_id, 50_000.0)
    assert ok["outcome"] == "sent"
    assert e.account(t.tenant_id)["balance"] == 200_000.0


def test_emd_fraud_held() -> None:
    e = _engine()
    t = e.provision("run-1")
    e.inject_fault(t.tenant_id, Fault(FaultType.FRAUD_FLAG, "P1", "fraud", "emd"))
    res = e.emd_release(t.tenant_id, 10_000.0)
    assert res["outcome"] == "held" and res["fault"]["type"] == "fraud_flag"


def test_audit_log_and_teardown() -> None:
    e = _engine()
    t = e.provision("run-1")
    e.apply(t.tenant_id, 1.0)
    assert len(e.audit_log(t.tenant_id)) >= 2  # provision + apply
    e.teardown(t.tenant_id)
    with pytest.raises(KeyError):
        e.account(t.tenant_id)
