"""CapitalForge adapter (blueprint §E.7) — Local (in-process Mock Bank) implementation.

Default dev/CI adapter. A real CapitalForge sandbox drops in as an HTTP-backed adapter behind
the same `ForgeAdapter` contract (settings.forge_capitalforge_sandbox_url); local is the v1
reality (same stub-first philosophy as ADR-0001).
"""

from __future__ import annotations

from datetime import datetime

from src.services.forges.base import Fault, FaultType, ForgeAdapter, SandboxTenant
from src.services.forges.mock_bank import MockBankEngine, mock_bank


class LocalCapitalForgeAdapter(ForgeAdapter):
    forge_name = "capitalforge"

    def __init__(self, engine: MockBankEngine | None = None) -> None:
        self.engine = engine or mock_bank

    async def health_check(self) -> dict:
        return {
            "forge": "capitalforge",
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
        return "capitalforge.mock.v1"

    async def inject_fault(self, tenant_id: str, fault: Fault) -> None:
        self.engine.inject_fault(tenant_id, fault)

    async def exercise(self, tenant_id: str, cap: str, fault_type: str | None) -> dict:
        module = cap.split(".")[1] if "." in cap else "bank"
        if fault_type:
            sev = "P0" if fault_type in (FaultType.NSF, FaultType.OFAC) else "P1"
            await self.inject_fault(
                tenant_id, Fault(fault_type, sev, f"{fault_type} on {module}", module)
            )
        if module == "emd":
            return await self.emd_release(tenant_id, 10_000.0)
        if module == "wire":
            return await self.wire(tenant_id, 300_000.0)
        return await self.apply(tenant_id, 200_000.0)

    # -- bank operations (used by the mock world) -------------------------

    async def apply(self, tenant_id: str, amount: float) -> dict:
        return self.engine.apply(tenant_id, amount)

    async def wire(self, tenant_id: str, amount: float) -> dict:
        return self.engine.wire(tenant_id, amount)

    async def emd_release(self, tenant_id: str, amount: float) -> dict:
        return self.engine.emd_release(tenant_id, amount)

    async def account(self, tenant_id: str) -> dict:
        return self.engine.account(tenant_id)
