"""Forges router — inspect Forge adapters + a CapitalForge demo flow (blueprint Part E)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.deps import require_role
from src.services.forges import Fault, FaultType
from src.services.forges.capitalforge import LocalCapitalForgeAdapter
from src.services.forges.registry import KNOWN_FORGES, get_forge_adapter

router = APIRouter()


class DemoBankRequest(BaseModel):
    fault: str | None = None  # declination|fraud_flag|nsf|ofac|velocity
    amount: float = 200000.0


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
    await adapter.teardown_sandbox_tenant(tenant.tenant_id)
    return {"tenant_id": tenant.tenant_id, "result": result, "audit_entries": len(audit)}
