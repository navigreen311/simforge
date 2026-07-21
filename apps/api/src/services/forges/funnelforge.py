"""FunnelForge adapter (blueprint §E.6) — Local (in-process Funnel) implementation.

Default dev/CI adapter. A real FunnelForge sandbox drops in as an HTTP + webhook-backed adapter
behind the same `ForgeAdapter` contract (settings.forge_funnelforge_sandbox_url).
"""

from __future__ import annotations

from datetime import datetime

from src.services.forges.base import Fault, ForgeAdapter, SandboxTenant
from src.services.forges.funnel import FunnelEngine, funnel


class LocalFunnelForgeAdapter(ForgeAdapter):
    forge_name = "funnelforge"

    def __init__(self, engine: FunnelEngine | None = None) -> None:
        self.engine = engine or funnel

    async def health_check(self) -> dict:
        return {
            "forge": "funnelforge",
            "ok": True,
            "mode": "local",
            "version": await self.get_current_version(),
        }

    async def provision_sandbox_tenant(self, run_id: str) -> SandboxTenant:
        return self.engine.provision(run_id)

    async def teardown_sandbox_tenant(self, tenant_id: str) -> None:
        self.engine.teardown(tenant_id)

    async def seed_state(self, tenant_id: str, fixtures: dict) -> None:
        self.engine.seed_state(tenant_id, fixtures)

    async def get_audit_log(self, tenant_id: str, since: datetime | None = None) -> list[dict]:
        log = self.engine.audit_log(tenant_id)
        if since is not None:
            log = [e for e in log if e["ts"] >= since.isoformat()]
        return log

    async def get_current_version(self) -> str:
        return "funnelforge.flows.v1"

    async def inject_fault(self, tenant_id: str, fault: Fault) -> None:
        # Start a flow in the fault's module and inject onto it, then it surfaces when run.
        flow = self.engine.start_flow(tenant_id, fault.module)
        self.engine.inject_fault(tenant_id, flow.flow_id, fault.fault_type)

    async def exercise(self, tenant_id: str, cap: str, fault_type: str | None) -> dict:
        module = cap.split(".")[1] if "." in cap else "sequences"
        return await self.trigger_and_run(tenant_id, module, fault_type)

    # -- flow operations (used by the mock world) -------------------------

    async def trigger_and_run(
        self, tenant_id: str, module: str, fault_type: str | None = None
    ) -> dict:
        if fault_type:
            return self.engine.inject_fault_on_flow(tenant_id, module, fault_type)
        flow = self.engine.start_flow(tenant_id, module)
        return self.engine.run_flow(tenant_id, flow.flow_id)
