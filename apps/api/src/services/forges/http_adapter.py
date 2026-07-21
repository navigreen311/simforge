"""HTTP-backed Forge adapter (ADR-0016).

Implements the `ForgeAdapter` contract against a **real** Forge sandbox over HTTP — the drop-in
that every Local adapter's docstring promises. The generic sandbox API (blueprint §E.1) is:

- ``GET  {base}/health``                                  → ``{"ok": bool, "version": str}``
- ``GET  {base}/version``                                 → ``{"version": str}``
- ``POST {base}/sandbox/tenants``                         → ``{"tenant_id": str}``
- ``DELETE {base}/sandbox/tenants/{id}``
- ``POST {base}/sandbox/tenants/{id}/seed-state``
- ``GET  {base}/sandbox/tenants/{id}/audit-log?since=``   → ``[{...}]``
- ``POST {base}/sandbox/tenants/{id}/faults``             (Fault body)
- ``POST {base}/sandbox/tenants/{id}/exercise``           → ``{"outcome": str, "fault"?: {...}}``

`reference_sandbox.create_reference_sandbox(forge)` is a conformant reference implementation of
this API (backed by the in-process Local engine), used to test this adapter hermetically.
"""

from __future__ import annotations

from datetime import datetime

import httpx

from src.services.forges.base import Fault, ForgeAdapter, SandboxTenant
from src.utils.time import utcnow


class HttpForgeAdapter(ForgeAdapter):
    def __init__(
        self,
        forge: str,
        base_url: str,
        *,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.forge_name = forge
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport  # tests inject an ASGI transport; prod leaves it None

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url, timeout=self._timeout, transport=self._transport
        )

    async def health_check(self) -> dict:
        try:
            async with self._client() as c:
                resp = await c.get("/health")
                resp.raise_for_status()
                body = resp.json()
            return {
                "forge": self.forge_name,
                "ok": bool(body.get("ok", True)),
                "mode": "http",
                "version": body.get("version"),
            }
        except (httpx.HTTPError, ValueError) as exc:
            return {
                "forge": self.forge_name,
                "ok": False,
                "mode": "http",
                "reason": f"sandbox unreachable: {type(exc).__name__}",
            }

    async def provision_sandbox_tenant(self, run_id: str) -> SandboxTenant:
        async with self._client() as c:
            resp = await c.post("/sandbox/tenants", json={"run_id": run_id})
            resp.raise_for_status()
            tenant_id = resp.json()["tenant_id"]
        return SandboxTenant(
            tenant_id=tenant_id, forge=self.forge_name, run_id=run_id, created_at=utcnow()
        )

    async def teardown_sandbox_tenant(self, tenant_id: str) -> None:
        async with self._client() as c:
            await c.delete(f"/sandbox/tenants/{tenant_id}")

    async def seed_state(self, tenant_id: str, fixtures: dict) -> None:
        async with self._client() as c:
            resp = await c.post(f"/sandbox/tenants/{tenant_id}/seed-state", json=fixtures)
            resp.raise_for_status()

    async def get_audit_log(self, tenant_id: str, since: datetime | None = None) -> list[dict]:
        params = {"since": since.isoformat()} if since is not None else None
        async with self._client() as c:
            resp = await c.get(f"/sandbox/tenants/{tenant_id}/audit-log", params=params)
            resp.raise_for_status()
            body = resp.json()
        return list(body) if isinstance(body, list) else list(body.get("events", []))

    async def get_current_version(self) -> str:
        async with self._client() as c:
            resp = await c.get("/version")
            resp.raise_for_status()
            return str(resp.json()["version"])

    async def inject_fault(self, tenant_id: str, fault: Fault) -> None:
        payload = {
            "fault_type": fault.fault_type,
            "severity": fault.severity,
            "detail": fault.detail,
            "module": fault.module,
        }
        async with self._client() as c:
            resp = await c.post(f"/sandbox/tenants/{tenant_id}/faults", json=payload)
            resp.raise_for_status()

    async def exercise(self, tenant_id: str, cap: str, fault_type: str | None) -> dict:
        async with self._client() as c:
            resp = await c.post(
                f"/sandbox/tenants/{tenant_id}/exercise", json={"cap": cap, "fault": fault_type}
            )
            resp.raise_for_status()
            return dict(resp.json())
