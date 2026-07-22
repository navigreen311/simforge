"""Consumer-driven Pact contract for the Forge sandbox HTTP boundary (ADR-0016 / ADR-0036).

Two halves of one contract, both hermetic (no broker, no network beyond localhost):

1. **Consumer** — `HttpForgeAdapter` (SimForge) drives a Pact mock provider, proving it sends the
   contracted requests and parses the contracted responses. This writes the pact file.
2. **Provider** — the `reference_sandbox` FastAPI app (the conformant reference every real Forge
   must match) is driven through the same API in-process, proving it honours the response shapes.

A change on either side that breaks the shared shape fails here.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
from pact import Pact

from src.services.forges.http_adapter import HttpForgeAdapter
from src.services.forges.reference_sandbox import create_reference_sandbox

PACT_DIR = Path(__file__).parent / "pacts"
PACT_FILE = PACT_DIR / "SimForgeForgeConsumer-ForgeSandbox.json"
FORGE = "capitalforge"


async def test_forge_sandbox_consumer_contract() -> None:
    """SimForge (consumer) honours the Forge sandbox contract; writes the pact file."""
    pact = Pact("SimForgeForgeConsumer", "ForgeSandbox").with_specification("V4")

    pact.upon_receiving("a version query").with_request("GET", "/version").will_respond_with(
        200
    ).with_body({"version": "capitalforge-1.0.0"})

    (
        pact.upon_receiving("a tenant provision")
        .with_request("POST", "/sandbox/tenants")
        .with_body({"run_id": "run-1"})
        .will_respond_with(200)
        .with_body({"tenant_id": "t-123", "forge": FORGE, "run_id": "run-1"})
    )

    (
        pact.upon_receiving("an exercise call")
        .with_request("POST", "/sandbox/tenants/t-123/exercise")
        .with_body({"cap": "capitalforge.mock_bank.transfer", "fault": None})
        .will_respond_with(200)
        .with_body({"outcome": "ok"})
    )

    with pact.serve() as srv:
        adapter = HttpForgeAdapter(FORGE, str(srv.url))  # real HTTP to the localhost mock
        assert await adapter.get_current_version() == "capitalforge-1.0.0"
        tenant = await adapter.provision_sandbox_tenant("run-1")
        assert tenant.tenant_id == "t-123"
        result = await adapter.exercise("t-123", "capitalforge.mock_bank.transfer", None)
        assert result["outcome"] == "ok"

    PACT_DIR.mkdir(parents=True, exist_ok=True)
    pact.write_file(PACT_DIR, overwrite=True)
    assert PACT_FILE.exists()


async def test_forge_sandbox_provider_conforms() -> None:
    """The reference sandbox (provider) honours the contracted response shapes."""
    app = create_reference_sandbox(FORGE)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://provider") as c:
        # /version → {"version": str}
        ver = (await c.get("/version")).json()
        assert isinstance(ver.get("version"), str) and ver["version"]

        # POST /sandbox/tenants → {tenant_id, forge, run_id}
        prov = (await c.post("/sandbox/tenants", json={"run_id": "run-1"})).json()
        assert {"tenant_id", "forge", "run_id"} <= prov.keys()
        assert prov["forge"] == FORGE
        tenant_id = prov["tenant_id"]

        # POST /sandbox/tenants/{id}/exercise → {"outcome": str, ["fault": {...}]}
        ex = (
            await c.post(
                f"/sandbox/tenants/{tenant_id}/exercise",
                json={"cap": "capitalforge.mock_bank.transfer", "fault": None},
            )
        ).json()
        assert isinstance(ex.get("outcome"), str) and ex["outcome"]


def test_pact_file_covers_the_provider_endpoints() -> None:
    """Cross-check: every interaction in the committed pact hits an endpoint the provider serves."""
    assert PACT_FILE.exists(), "run the consumer test first to generate the pact file"
    pact = json.loads(PACT_FILE.read_text(encoding="utf-8"))
    app = create_reference_sandbox(FORGE)
    served_paths = {
        route.path for route in app.routes if hasattr(route, "path")  # type: ignore[attr-defined]
    }
    # Template the concrete tenant id back to the provider's path param for the membership check.
    for interaction in pact["interactions"]:
        path = interaction["request"]["path"]
        normalized = path.replace("/t-123", "/{tenant_id}")
        assert normalized in served_paths, f"provider does not serve {path}"
