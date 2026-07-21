"""CRE Forge adapter (blueprint §E.5) — Local (in-process Deal Desk) implementation.

Default dev/CI adapter. A real CRE Forge sandbox drops in as an HTTP-backed adapter behind the
same `ForgeAdapter` contract (settings.forge_cre_forge_sandbox_url).
"""

from __future__ import annotations

from datetime import datetime

from src.services.forges.base import Fault, ForgeAdapter, SandboxTenant
from src.services.forges.deal_desk import DealDeskEngine, deal_desk


class LocalCREForgeAdapter(ForgeAdapter):
    forge_name = "cre-forge"

    def __init__(self, engine: DealDeskEngine | None = None) -> None:
        self.engine = engine or deal_desk

    async def health_check(self) -> dict:
        return {
            "forge": "cre-forge",
            "ok": True,
            "mode": "local",
            "version": await self.get_current_version(),
        }

    async def provision_sandbox_tenant(self, run_id: str) -> SandboxTenant:
        return self.engine.provision(run_id)

    async def teardown_sandbox_tenant(self, tenant_id: str) -> None:
        self.engine.teardown(tenant_id)

    async def seed_state(self, tenant_id: str, fixtures: dict) -> None:
        for deal_type in fixtures.get("deal_types", []):
            self.engine.create_deal(tenant_id, deal_type)

    async def get_audit_log(self, tenant_id: str, since: datetime | None = None) -> list[dict]:
        log = self.engine.audit_log(tenant_id)
        if since is not None:
            log = [e for e in log if e["ts"] >= since.isoformat()]
        return log

    async def get_current_version(self) -> str:
        return "cre-forge.dealdesk.v1"

    async def inject_fault(self, tenant_id: str, fault: Fault) -> None:
        # Create a deal of the fault's module (deal_type) and inject onto it, then it processes.
        deal = self.engine.create_deal(tenant_id, fault.module)
        self.engine.inject_fault(tenant_id, deal.deal_id, fault.fault_type)

    # -- deal operations (used by the mock world) -------------------------

    async def create_and_process(
        self, tenant_id: str, deal_type: str, fault_type: str | None = None
    ) -> dict:
        if fault_type:
            return self.engine.inject_fault_on_deal(tenant_id, deal_type, fault_type)
        deal = self.engine.create_deal(tenant_id, deal_type)
        return self.engine.process_deal(tenant_id, deal.deal_id)
