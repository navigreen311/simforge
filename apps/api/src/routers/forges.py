"""Forges router — inspect Forge adapters + a CapitalForge demo flow (blueprint Part E)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.deps import require_role
from src.services.forges import Fault, FaultType
from src.services.forges.capitalforge import LocalCapitalForgeAdapter
from src.services.forges.cre_forge import LocalCREForgeAdapter
from src.services.forges.funnelforge import LocalFunnelForgeAdapter
from src.services.forges.medlink_pro import LocalMedLinkProAdapter
from src.services.forges.registry import KNOWN_FORGES, get_forge_adapter
from src.services.forges.visionaudioforge import LocalVAFAdapter
from src.services.forges.voiceforge import LocalVoiceForgeAdapter

router = APIRouter()


class DemoBankRequest(BaseModel):
    fault: str | None = None  # declination|fraud_flag|nsf|ofac|velocity
    amount: float = 200000.0


class DemoDocRequest(BaseModel):
    fault: str | None = None  # forged_signature|expired_date|revoked_license|oig_match|...
    doc_type: str = "title_report"


class DemoCallRequest(BaseModel):
    fault: str | None = None  # dropped_call|dead_air|misroute|disclosure_missing|...
    direction: str = "inbound"


class DemoDealRequest(BaseModel):
    fault: str | None = None  # title_defect|lien_undisclosed|assignment_blocked|deal_stale|...
    deal_type: str = "assignment"


class DemoConsoleRequest(BaseModel):
    fault: str | None = (
        None  # credential_expired_unflagged|shift_double_booked|ui_blocking_modal|...
    )
    module: str = "scheduler"


class DemoFlowRequest(BaseModel):
    fault: str | None = None  # webhook_dropped|campaign_to_unsubscribed|sequence_misfire|...
    module: str = "sequences"


@router.get("/", dependencies=[Depends(require_role("viewer"))])
async def list_forges() -> dict:
    forges = []
    for name in KNOWN_FORGES:
        health = await get_forge_adapter(name).health_check()
        forges.append({"forge": name, **health})
    return {"forges": forges}


@router.get("/{forge}/health", dependencies=[Depends(require_role("viewer"))])
async def forge_health(forge: str) -> dict:
    return await get_forge_adapter(forge).health_check()


@router.post("/capitalforge/demo", dependencies=[Depends(require_role("admin"))])
async def capitalforge_demo(body: DemoBankRequest) -> dict:
    """Provision a Mock Bank tenant, optionally inject a fault, run a credit application."""
    adapter = LocalCapitalForgeAdapter()
    tenant = await adapter.provision_sandbox_tenant("demo")
    if body.fault:
        sev = "P0" if body.fault in (FaultType.NSF, FaultType.OFAC) else "P1"
        await adapter.inject_fault(
            tenant.tenant_id, Fault(body.fault, sev, f"injected {body.fault}", "bank")
        )
    result = await adapter.apply(tenant.tenant_id, body.amount)
    audit = await adapter.get_audit_log(tenant.tenant_id)
    world = await adapter.world_state(tenant.tenant_id)
    await adapter.teardown_sandbox_tenant(tenant.tenant_id)
    return {
        "tenant_id": tenant.tenant_id,
        "result": result,
        "audit_entries": len(audit),
        "world": world,
    }


@router.post("/vaf/demo", dependencies=[Depends(require_role("admin"))])
async def vaf_demo(body: DemoDocRequest) -> dict:
    """Provision a Doc Vault tenant, retrieve a doc, optionally with an injected doc fault."""
    adapter = LocalVAFAdapter()
    tenant = await adapter.provision_sandbox_tenant("demo")
    result = await adapter.generate_and_extract(tenant.tenant_id, body.doc_type, body.fault)
    audit = await adapter.get_audit_log(tenant.tenant_id)
    world = await adapter.world_state(tenant.tenant_id)
    await adapter.teardown_sandbox_tenant(tenant.tenant_id)
    return {
        "tenant_id": tenant.tenant_id,
        "result": result,
        "audit_entries": len(audit),
        "world": world,
    }


@router.post("/voiceforge/demo", dependencies=[Depends(require_role("admin"))])
async def voiceforge_demo(body: DemoCallRequest) -> dict:
    """Provision a Call Center tenant, place+handle a call, optionally with an injected fault."""
    adapter = LocalVoiceForgeAdapter()
    tenant = await adapter.provision_sandbox_tenant("demo")
    result = await adapter.place_and_handle(tenant.tenant_id, body.direction, body.fault)
    audit = await adapter.get_audit_log(tenant.tenant_id)
    world = await adapter.world_state(tenant.tenant_id)
    await adapter.teardown_sandbox_tenant(tenant.tenant_id)
    return {
        "tenant_id": tenant.tenant_id,
        "result": result,
        "audit_entries": len(audit),
        "world": world,
    }


@router.post("/cre-forge/demo", dependencies=[Depends(require_role("admin"))])
async def cre_forge_demo(body: DemoDealRequest) -> dict:
    """Provision a Deal Desk tenant, process a deal, optionally with an injected deal fault."""
    adapter = LocalCREForgeAdapter()
    tenant = await adapter.provision_sandbox_tenant("demo")
    result = await adapter.create_and_process(tenant.tenant_id, body.deal_type, body.fault)
    audit = await adapter.get_audit_log(tenant.tenant_id)
    world = await adapter.world_state(tenant.tenant_id)
    await adapter.teardown_sandbox_tenant(tenant.tenant_id)
    return {
        "tenant_id": tenant.tenant_id,
        "result": result,
        "audit_entries": len(audit),
        "world": world,
    }


@router.post("/medlink-pro/demo", dependencies=[Depends(require_role("admin"))])
async def medlink_pro_demo(body: DemoConsoleRequest) -> dict:
    """Provision a Clinical Console tenant, run a task, optionally with an injected fault."""
    adapter = LocalMedLinkProAdapter()
    tenant = await adapter.provision_sandbox_tenant("demo")
    result = await adapter.start_and_run(tenant.tenant_id, body.module, body.fault)
    audit = await adapter.get_audit_log(tenant.tenant_id)
    world = await adapter.world_state(tenant.tenant_id)
    await adapter.teardown_sandbox_tenant(tenant.tenant_id)
    return {
        "tenant_id": tenant.tenant_id,
        "result": result,
        "audit_entries": len(audit),
        "world": world,
    }


@router.post("/funnelforge/demo", dependencies=[Depends(require_role("admin"))])
async def funnelforge_demo(body: DemoFlowRequest) -> dict:
    """Provision a Funnel tenant, trigger+run a flow, optionally with an injected flow fault."""
    adapter = LocalFunnelForgeAdapter()
    tenant = await adapter.provision_sandbox_tenant("demo")
    result = await adapter.trigger_and_run(tenant.tenant_id, body.module, body.fault)
    audit = await adapter.get_audit_log(tenant.tenant_id)
    world = await adapter.world_state(tenant.tenant_id)
    await adapter.teardown_sandbox_tenant(tenant.tenant_id)
    return {
        "tenant_id": tenant.tenant_id,
        "result": result,
        "audit_entries": len(audit),
        "world": world,
    }
