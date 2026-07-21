"""SimForge FastAPI application factory (blueprint §C.1).

Phase 1 wires health + agents + departments. Remaining routers (packs, scenarios, runs,
certs, snapshots, gaps, dashboard, registry, lineage, constitution, attest) are added per
the ROADMAP as their services land.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.db import dispose_engine
from src.routers import (
    agents,
    attest,
    certs,
    departments,
    gaps,
    health,
    packs,
    runs,
    scenarios,
)
from src.telemetry.logging import configure_logging
from src.telemetry.metrics import configure_metrics
from src.telemetry.tracing import configure_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    configure_logging()
    configure_tracing()
    configure_metrics()
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title="SimForge API",
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api/health", tags=["health"])
    app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
    app.include_router(departments.router, prefix="/api/departments", tags=["departments"])
    app.include_router(packs.router, prefix="/api/packs", tags=["packs"])
    app.include_router(scenarios.router, prefix="/api/scenarios", tags=["scenarios"])
    app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
    app.include_router(gaps.router, prefix="/api/gaps", tags=["gaps"])
    app.include_router(certs.router, prefix="/api/certs", tags=["certs"])
    app.include_router(certs.snapshots_router, prefix="/api/snapshots", tags=["snapshots"])
    app.include_router(attest.router, prefix="/api/attest", tags=["attestation"])

    return app


app = create_app()
