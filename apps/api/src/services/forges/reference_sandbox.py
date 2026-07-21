"""Reference Forge-sandbox HTTP server (ADR-0016).

A conformant implementation of the generic sandbox API (see `http_adapter`) that any real Forge
sandbox must expose, backed by the in-process **Local** engine for the named forge. It lets us:

- test `HttpForgeAdapter` hermetically (round-trip HTTP → engine → HTTP, no network), and
- run a stand-in sandbox locally (`scripts/run-forge-sandbox.py`) so a dev can point
  `FORGE_MODE=http` + `FORGE_SANDBOX_URLS` at it and exercise the real HTTP path.

This is a **reference/dev** server — a production Forge implements the same contract for real.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.services.forges.base import Fault
from src.services.forges.registry import local_forge_adapter


class _FaultBody(BaseModel):
    fault_type: str
    severity: str = "P1"
    detail: str = ""
    module: str = "core"


class _ExerciseBody(BaseModel):
    cap: str
    fault: str | None = None


def create_reference_sandbox(forge: str) -> FastAPI:
    """A FastAPI app implementing the generic sandbox API for `forge` via its Local engine."""
    app = FastAPI(title=f"reference-forge-sandbox:{forge}")
    adapter = local_forge_adapter(forge)

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True, "version": await adapter.get_current_version()}

    @app.get("/version")
    async def version() -> dict:
        return {"version": await adapter.get_current_version()}

    @app.post("/sandbox/tenants")
    async def provision(body: dict) -> dict:
        tenant = await adapter.provision_sandbox_tenant(body.get("run_id", "http"))
        return {"tenant_id": tenant.tenant_id, "forge": tenant.forge, "run_id": tenant.run_id}

    @app.delete("/sandbox/tenants/{tenant_id}")
    async def teardown(tenant_id: str) -> dict:
        await adapter.teardown_sandbox_tenant(tenant_id)
        return {"ok": True}

    @app.post("/sandbox/tenants/{tenant_id}/seed-state")
    async def seed_state(tenant_id: str, body: dict) -> dict:
        await adapter.seed_state(tenant_id, body)
        return {"ok": True}

    @app.get("/sandbox/tenants/{tenant_id}/audit-log")
    async def audit_log(tenant_id: str) -> list[dict]:
        try:
            return await adapter.get_audit_log(tenant_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="unknown tenant") from exc

    @app.post("/sandbox/tenants/{tenant_id}/faults")
    async def inject_fault(tenant_id: str, body: _FaultBody) -> dict:
        await adapter.inject_fault(
            tenant_id, Fault(body.fault_type, body.severity, body.detail, body.module)
        )
        return {"ok": True}

    @app.post("/sandbox/tenants/{tenant_id}/exercise")
    async def exercise(tenant_id: str, body: _ExerciseBody) -> dict:
        return await adapter.exercise(tenant_id, body.cap, body.fault)

    return app
