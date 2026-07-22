"""Run the reference Forge sandbox server (ADR-0016 / ADR-0037).

Serves a conformant HTTP sandbox for every known forge, each mounted under ``/{forge}``, backed by
that forge's in-process Local engine. Point the API at it to activate the real HTTP Forge seam:

    # terminal 1 — the sandbox (default :8850)
    cd apps/api && python scripts/run-forge-sandbox.py

    # terminal 2 — the API in http mode, one URL per forge
    FORGE_MODE=http \
    FORGE_SANDBOX_URLS="capitalforge=http://127.0.0.1:8850/capitalforge" \
    uvicorn src.main:app

Then `GET /api/forges` reports mode=http and runs exercise the real HTTP path. This is a *reference*
server; a production Forge implements the same contract (see tests/contract, ADR-0036).
"""

from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI

from src.services.forges.reference_sandbox import create_reference_sandbox
from src.services.forges.registry import KNOWN_FORGES


def build_app() -> FastAPI:
    app = FastAPI(title="reference-forge-sandbox")

    @app.get("/")
    async def index() -> dict:
        return {"forges": list(KNOWN_FORGES), "mount": "/{forge}"}

    for forge in KNOWN_FORGES:
        app.mount(f"/{forge}", create_reference_sandbox(forge))
    return app


app = build_app()


if __name__ == "__main__":
    port = int(os.environ.get("FORGE_SANDBOX_PORT", "8850"))
    uvicorn.run(app, host="127.0.0.1", port=port)
