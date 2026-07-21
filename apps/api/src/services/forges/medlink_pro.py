"""medlink-pro adapter (blueprint §E.4) — Local (in-process Clinical Console) implementation.

Default dev/CI adapter. A real medlink-pro sandbox drops in as an HTTP-backed adapter behind the
same `ForgeAdapter` contract (settings.forge_medlink_pro_sandbox_url). Fixtures are PHI-synthetic
only — never real PHI.
"""

from __future__ import annotations

from datetime import datetime

from src.services.forges.base import Fault, ForgeAdapter, SandboxTenant
from src.services.forges.clinical_console import ClinicalConsoleEngine, clinical_console


class LocalMedLinkProAdapter(ForgeAdapter):
    forge_name = "medlink-pro"

    def __init__(self, engine: ClinicalConsoleEngine | None = None) -> None:
        self.engine = engine or clinical_console

    async def health_check(self) -> dict:
        return {
            "forge": "medlink-pro",
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
        return "medlink-pro.console.v1"

    async def inject_fault(self, tenant_id: str, fault: Fault) -> None:
        # Start a task in the fault's module and inject onto it, then it surfaces when run.
        task = self.engine.start_task(tenant_id, fault.module)
        self.engine.inject_fault(tenant_id, task.task_id, fault.fault_type)

    async def exercise(self, tenant_id: str, cap: str, fault_type: str | None) -> dict:
        module = cap.split(".")[1] if "." in cap else "scheduler"
        return await self.start_and_run(tenant_id, module, fault_type)

    # -- console operations (used by the mock world) ----------------------

    async def start_and_run(
        self, tenant_id: str, module: str, fault_type: str | None = None
    ) -> dict:
        if fault_type:
            return self.engine.inject_fault_on_task(tenant_id, module, fault_type)
        task = self.engine.start_task(tenant_id, module)
        return self.engine.run_task(tenant_id, task.task_id)
