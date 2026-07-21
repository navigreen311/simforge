"""Contract tests for the Forge adapter (§I.3) — CapitalForge + VAF + VoiceForge + Null."""

from __future__ import annotations

import pytest

from src.services.forges.base import Fault, FaultType, NullForgeAdapter
from src.services.forges.call_center import CallCenterEngine
from src.services.forges.capitalforge import LocalCapitalForgeAdapter
from src.services.forges.clinical_console import ClinicalConsoleEngine
from src.services.forges.cre_forge import LocalCREForgeAdapter
from src.services.forges.deal_desk import DealDeskEngine
from src.services.forges.doc_vault import DocVaultEngine
from src.services.forges.medlink_pro import LocalMedLinkProAdapter
from src.services.forges.mock_bank import MockBankEngine
from src.services.forges.registry import forge_of_cap, get_forge_adapter
from src.services.forges.visionaudioforge import LocalVAFAdapter
from src.services.forges.voiceforge import LocalVoiceForgeAdapter


def test_registry_resolves_real_forges_and_null() -> None:
    assert isinstance(get_forge_adapter("capitalforge"), LocalCapitalForgeAdapter)
    assert isinstance(get_forge_adapter("vaf"), LocalVAFAdapter)
    assert isinstance(get_forge_adapter("voiceforge"), LocalVoiceForgeAdapter)
    assert isinstance(get_forge_adapter("cre-forge"), LocalCREForgeAdapter)
    assert isinstance(get_forge_adapter("medlink-pro"), LocalMedLinkProAdapter)
    assert isinstance(get_forge_adapter("funnelforge"), NullForgeAdapter)
    assert forge_of_cap("capitalforge.emd.release") == "capitalforge"
    assert forge_of_cap("vaf.doc_vault.retrieve") == "vaf"
    assert forge_of_cap("voiceforge.call_center.inbound") == "voiceforge"
    assert forge_of_cap("cre-forge.deals.title") == "cre-forge"
    assert forge_of_cap("medlink-pro.scheduler.shift_fill") == "medlink-pro"


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


async def test_voiceforge_adapter_contract() -> None:
    adapter = LocalVoiceForgeAdapter(CallCenterEngine())

    health = await adapter.health_check()
    assert health["ok"] is True and health["mode"] == "local"
    assert await adapter.get_current_version() == "voiceforge.callcenter.v1"

    tenant = await adapter.provision_sandbox_tenant("run-z")
    assert tenant.forge == "voiceforge" and tenant.run_id == "run-z"

    await adapter.seed_state(tenant.tenant_id, {"calls": [{"direction": "inbound"}]})

    # Clean call → handled, no fault.
    clean = await adapter.place_and_handle(tenant.tenant_id, "inbound")
    assert clean["outcome"] == "handled" and "fault" not in clean

    # Dropped call → handling surfaces a P0 fault.
    faulted = await adapter.place_and_handle(tenant.tenant_id, "inbound", FaultType.DROPPED_CALL)
    assert faulted["outcome"] == "fault_detected"
    assert faulted["fault"]["type"] == FaultType.DROPPED_CALL
    assert faulted["fault"]["severity"] == "P0"

    log = await adapter.get_audit_log(tenant.tenant_id)
    assert any(e["action"] == "inject_fault" for e in log)

    await adapter.teardown_sandbox_tenant(tenant.tenant_id)


async def test_cre_forge_adapter_contract() -> None:
    adapter = LocalCREForgeAdapter(DealDeskEngine())

    health = await adapter.health_check()
    assert health["ok"] is True and health["mode"] == "local"
    assert await adapter.get_current_version() == "cre-forge.dealdesk.v1"

    tenant = await adapter.provision_sandbox_tenant("run-w")
    assert tenant.forge == "cre-forge" and tenant.run_id == "run-w"

    await adapter.seed_state(tenant.tenant_id, {"deal_types": ["assignment"]})

    # Clean deal → clear, no fault.
    clean = await adapter.create_and_process(tenant.tenant_id, "assignment")
    assert clean["outcome"] == "clear" and "fault" not in clean

    # Title defect → processing surfaces a P0 fault.
    faulted = await adapter.create_and_process(
        tenant.tenant_id, "assignment", FaultType.TITLE_DEFECT
    )
    assert faulted["outcome"] == "fault_detected"
    assert faulted["fault"]["type"] == FaultType.TITLE_DEFECT
    assert faulted["fault"]["severity"] == "P0"

    log = await adapter.get_audit_log(tenant.tenant_id)
    assert any(e["action"] == "inject_fault" for e in log)

    await adapter.teardown_sandbox_tenant(tenant.tenant_id)


async def test_medlink_pro_adapter_contract() -> None:
    adapter = LocalMedLinkProAdapter(ClinicalConsoleEngine())

    health = await adapter.health_check()
    assert health["ok"] is True and health["mode"] == "local"
    assert await adapter.get_current_version() == "medlink-pro.console.v1"

    tenant = await adapter.provision_sandbox_tenant("run-v")
    assert tenant.forge == "medlink-pro" and tenant.run_id == "run-v"

    await adapter.seed_state(tenant.tenant_id, {"creds_expiring_days": 10})

    # Clean task → ok, no fault.
    clean = await adapter.start_and_run(tenant.tenant_id, "scheduler")
    assert clean["outcome"] == "ok" and "fault" not in clean

    # Unflagged expired credential → running the task surfaces a P0 fault.
    faulted = await adapter.start_and_run(
        tenant.tenant_id, "compliance", FaultType.CREDENTIAL_EXPIRED_UNFLAGGED
    )
    assert faulted["outcome"] == "fault_detected"
    assert faulted["fault"]["type"] == FaultType.CREDENTIAL_EXPIRED_UNFLAGGED
    assert faulted["fault"]["severity"] == "P0"

    # Fixtures are PHI-synthetic only.
    assert clean["fields"]["clinician"] == "SYNTHETIC CLINICIAN"

    log = await adapter.get_audit_log(tenant.tenant_id)
    assert any(e["action"] == "inject_fault" for e in log)

    await adapter.teardown_sandbox_tenant(tenant.tenant_id)


async def test_null_adapter_unhealthy_and_refuses() -> None:
    adapter = get_forge_adapter("funnelforge")
    assert (await adapter.health_check())["ok"] is False
    with pytest.raises(NotImplementedError):
        await adapter.provision_sandbox_tenant("run-x")
