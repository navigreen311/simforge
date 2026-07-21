"""VoiceForge adapter (blueprint §E.2) — Local (in-process Call Center) implementation.

Default dev/CI adapter. A real VoiceForge sandbox drops in as an HTTP/WebSocket-backed adapter
behind the same `ForgeAdapter` contract (settings.forge_voiceforge_sandbox_url).
"""

from __future__ import annotations

from datetime import datetime

from src.services.forges.base import Fault, ForgeAdapter, SandboxTenant
from src.services.forges.call_center import CallCenterEngine, call_center


class LocalVoiceForgeAdapter(ForgeAdapter):
    forge_name = "voiceforge"

    def __init__(self, engine: CallCenterEngine | None = None) -> None:
        self.engine = engine or call_center

    async def health_check(self) -> dict:
        return {
            "forge": "voiceforge",
            "ok": True,
            "mode": "local",
            "version": await self.get_current_version(),
        }

    async def provision_sandbox_tenant(self, run_id: str) -> SandboxTenant:
        return self.engine.provision(run_id)

    async def teardown_sandbox_tenant(self, tenant_id: str) -> None:
        self.engine.teardown(tenant_id)

    async def seed_state(self, tenant_id: str, fixtures: dict) -> None:
        for call in fixtures.get("calls", []):
            self.engine.place_call(tenant_id, call.get("direction", "inbound"), call.get("persona"))

    async def get_audit_log(self, tenant_id: str, since: datetime | None = None) -> list[dict]:
        log = self.engine.audit_log(tenant_id)
        if since is not None:
            log = [e for e in log if e["ts"] >= since.isoformat()]
        return log

    async def get_current_version(self) -> str:
        return "voiceforge.callcenter.v1"

    async def inject_fault(self, tenant_id: str, fault: Fault) -> None:
        # Place a call and inject the fault onto it, so it surfaces when handled.
        call = self.engine.place_call(tenant_id, "inbound")
        self.engine.inject_fault(tenant_id, call.call_id, fault.fault_type)

    # -- call operations (used by the mock world) -------------------------

    async def place_and_handle(
        self,
        tenant_id: str,
        direction: str,
        fault_type: str | None = None,
        persona: str | None = None,
    ) -> dict:
        if fault_type:
            return self.engine.inject_fault_on_call(tenant_id, direction, fault_type, persona)
        call = self.engine.place_call(tenant_id, direction, persona)
        return self.engine.handle_call(tenant_id, call.call_id)

    async def prosody_score(self, tenant_id: str) -> dict:
        return self.engine.prosody_score(tenant_id)
