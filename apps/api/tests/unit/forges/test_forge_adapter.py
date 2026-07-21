"""Contract tests for the Forge adapter (blueprint §I.3) — CapitalForge + VAF + Null."""

from __future__ import annotations

import pytest

from src.services.forges.base import Fault, FaultType, NullForgeAdapter
from src.services.forges.capitalforge import LocalCapitalForgeAdapter
from src.services.forges.doc_vault import DocVaultEngine
from src.services.forges.mock_bank import MockBankEngine
from src.services.forges.registry import forge_of_cap, get_forge_adapter
from src.services.forges.visionaudioforge import LocalVAFAdapter


def test_registry_resolves_capitalforge_vaf_and_null() -> None:
    assert isinstance(get_forge_adapter("capitalforge"), LocalCapitalForgeAdapter)
    assert isinstance(get_forge_adapter("vaf"), LocalVAFAdapter)
    assert isinstance(get_forge_adapter("voiceforge"), NullForgeAdapter)
    assert forge_of_cap("capitalforge.emd.release") == "capitalforge"
    assert forge_of_cap("vaf.doc_vault.retrieve") == "vaf"


async def test_capitalforge_adapter_contract() -> None:
    adapter = LocalCapitalForgeAdapter(MockBankEngine())

    health = await adapter.health_check()
    assert health["ok"] is True and health["mode"] == "local"
    assert await adapter.get_current_version() == "capitalforge.mock.v1"

    tenant = await adapter.provision_sandbox_tenant("run-x")
    assert tenant.forge == "capitalforge" and tenant.run_id == "run-x"

    await adapter.seed_state(tenant.tenant_id, {"balance": 100.0})
    await adapter.inject_fault(
        tenant.tenant_id, Fault(FaultType.DECLINATION, "P1", "declined", "bank")
    )
    result = await adapter.apply(tenant.tenant_id, 50.0)
    assert result["outcome"] == "declined"

    log = await adapter.get_audit_log(tenant.tenant_id)
    assert any(e["action"] == "inject_fault" for e in log)

    await adapter.teardown_sandbox_tenant(tenant.tenant_id)


async def test_vaf_adapter_contract() -> None:
    adapter = LocalVAFAdapter(DocVaultEngine())

    health = await adapter.health_check()
    assert health["ok"] is True and health["mode"] == "local"
    assert await adapter.get_current_version() == "vaf.docvault.v1"

    tenant = await adapter.provision_sandbox_tenant("run-y")
    assert tenant.forge == "vaf" and tenant.run_id == "run-y"

    await adapter.seed_state(tenant.tenant_id, {"doc_types": ["nursing_license"]})

    # Clean retrieval → no fault.
    clean = await adapter.generate_and_extract(tenant.tenant_id, "title_report")
    assert clean["outcome"] == "clean" and "fault" not in clean

    # Forged signature → OCR surfaces a P0 fault.
    faulted = await adapter.generate_and_extract(
        tenant.tenant_id, "title_report", FaultType.FORGED_SIGNATURE
    )
    assert faulted["outcome"] == "fault_detected"
    assert faulted["fault"]["type"] == FaultType.FORGED_SIGNATURE
    assert faulted["fault"]["severity"] == "P0"

    # Fixtures are synthetic only — never real PHI.
    assert clean["fields"]["name"] == "SYNTHETIC PERSON"

    log = await adapter.get_audit_log(tenant.tenant_id)
    assert any(e["action"] == "inject_fault" for e in log)

    await adapter.teardown_sandbox_tenant(tenant.tenant_id)


async def test_null_adapter_unhealthy_and_refuses() -> None:
    adapter = get_forge_adapter("cre-forge")
    assert (await adapter.health_check())["ok"] is False
    with pytest.raises(NotImplementedError):
        await adapter.provision_sandbox_tenant("run-x")
