"""Contract tests for HttpForgeAdapter — round-trip HTTP against the reference sandbox (ADR-0016).

Fully hermetic: httpx talks to the reference sandbox ASGI app in-process (no network).
"""

from __future__ import annotations

import httpx
import pytest

from src.services.forges.base import Fault, FaultType
from src.services.forges.http_adapter import HttpForgeAdapter
from src.services.forges.reference_sandbox import create_reference_sandbox


def _adapter(forge: str) -> HttpForgeAdapter:
    transport = httpx.ASGITransport(app=create_reference_sandbox(forge))
    return HttpForgeAdapter(forge, "http://sandbox.local", transport=transport)


async def test_http_adapter_full_round_trip() -> None:
    adapter = _adapter("capitalforge")

    assert await adapter.get_current_version() == "capitalforge.mock.v1"
    health = await adapter.health_check()
    assert health["ok"] is True and health["mode"] == "http"
    assert health["version"] == "capitalforge.mock.v1"

    tenant = await adapter.provision_sandbox_tenant("run-http")
    assert tenant.forge == "capitalforge" and tenant.run_id == "run-http"

    await adapter.seed_state(tenant.tenant_id, {"balance": 100.0})

    # Exercise clean → approved, no fault.
    clean = await adapter.exercise(tenant.tenant_id, "capitalforge.bank.apply", None)
    assert clean["outcome"] == "approved" and "fault" not in clean

    # Exercise with an injected fault → the sandbox surfaces it over HTTP.
    faulted = await adapter.exercise(
        tenant.tenant_id, "capitalforge.emd.release", FaultType.FRAUD_FLAG
    )
    assert faulted["outcome"] == "held"
    assert faulted["fault"]["type"] == "fraud_flag"

    # Audit log crosses the wire too.
    log = await adapter.get_audit_log(tenant.tenant_id)
    assert any(e["action"] == "provision" for e in log)

    await adapter.teardown_sandbox_tenant(tenant.tenant_id)


async def test_http_adapter_inject_fault_endpoint() -> None:
    adapter = _adapter("vaf")
    tenant = await adapter.provision_sandbox_tenant("run-http")
    await adapter.inject_fault(
        tenant.tenant_id, Fault(FaultType.FORGED_SIGNATURE, "P0", "forged", "title_report")
    )
    log = await adapter.get_audit_log(tenant.tenant_id)
    assert any(e["action"] == "inject_fault" for e in log)
    await adapter.teardown_sandbox_tenant(tenant.tenant_id)


@pytest.mark.parametrize(
    "forge", ["capitalforge", "vaf", "voiceforge", "cre-forge", "medlink-pro", "funnelforge"]
)
async def test_http_adapter_exercise_all_forges(forge: str) -> None:
    """Every forge's exercise op works over HTTP and surfaces an injected fault."""
    adapter = _adapter(forge)
    tenant = await adapter.provision_sandbox_tenant("run-http")
    # Pick each forge's default cap module + a valid fault for it.
    caps_and_faults = {
        "capitalforge": ("capitalforge.bank.apply", FaultType.DECLINATION),
        "vaf": ("vaf.doc_vault.retrieve", FaultType.FORGED_SIGNATURE),
        "voiceforge": ("voiceforge.call_center.inbound", FaultType.DROPPED_CALL),
        "cre-forge": ("cre-forge.deals.title", FaultType.TITLE_DEFECT),
        "medlink-pro": ("medlink-pro.scheduler.shift_fill", FaultType.SHIFT_DOUBLE_BOOKED),
        "funnelforge": ("funnelforge.sequences.trigger", FaultType.SEQUENCE_MISFIRE),
    }
    cap, fault = caps_and_faults[forge]
    result = await adapter.exercise(tenant.tenant_id, cap, fault)
    # Outcome strings are domain-specific (e.g. capitalforge "declined"); the fault dict is the
    # uniform signal the runner keys on.
    assert result["fault"]["type"] == fault
    await adapter.teardown_sandbox_tenant(tenant.tenant_id)


async def test_http_adapter_unreachable_sandbox_reports_unhealthy() -> None:
    def _raise(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    adapter = HttpForgeAdapter(
        "capitalforge", "http://down.local", transport=httpx.MockTransport(_raise)
    )
    health = await adapter.health_check()
    assert health["ok"] is False and health["mode"] == "http"
    assert "unreachable" in health["reason"]
