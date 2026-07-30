"""SimForge FastAPI application factory (blueprint §C.1).

Phase 1 wires health + agents + departments. Remaining routers (packs, scenarios, runs,
certs, snapshots, gaps, dashboard, registry, lineage, constitution, attest) are added per
the ROADMAP as their services land.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.db import dispose_engine
from src.routers import (
    adversarial,
    agents,
    attest,
    budget,
    capabilities,
    certs,
    cohort,
    constitution,
    dashboard,
    departments,
    drift,
    execution,
    forges,
    gaps,
    golden,
    health,
    incident,
    jurisdictions,
    locales,
    meta_eval,
    narrative,
    packs,
    pdp,
    registry,
    regression,
    runs,
    scenario_bank,
    scenarios,
    training,
    ventures,
)
from src.telemetry.logging import configure_logging
from src.telemetry.metrics import configure_metrics
from src.telemetry.tracing import configure_tracing, instrument_app


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
    app.include_router(ventures.router, prefix="/api/ventures", tags=["ventures"])
    app.include_router(scenarios.router, prefix="/api/scenarios", tags=["scenarios"])
    app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
    app.include_router(gaps.router, prefix="/api/gaps", tags=["gaps"])
    app.include_router(certs.router, prefix="/api/certs", tags=["certs"])
    app.include_router(certs.snapshots_router, prefix="/api/snapshots", tags=["snapshots"])
    app.include_router(attest.router, prefix="/api/attest", tags=["attestation"])
    app.include_router(constitution.router, prefix="/api/constitution", tags=["constitution"])
    app.include_router(registry.router, prefix="/api/registry", tags=["registry"])
    app.include_router(registry.lineage_router, prefix="/api/lineage", tags=["lineage"])
    app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
    app.include_router(forges.router, prefix="/api/forges", tags=["forges"])
    app.include_router(drift.router, prefix="/api/drift", tags=["drift"])
    app.include_router(regression.router, prefix="/api/regression", tags=["regression"])
    app.include_router(jurisdictions.router, prefix="/api/jurisdictions", tags=["jurisdictions"])
    app.include_router(pdp.router, prefix="/api/pdp", tags=["pdp"])
    app.include_router(execution.router, prefix="/api/execution", tags=["execution"])
    app.include_router(training.router, prefix="/api/training", tags=["training"])
    app.include_router(meta_eval.router, prefix="/api/meta-eval", tags=["meta-eval"])
    app.include_router(adversarial.router, prefix="/api/adversarial", tags=["adversarial"])
    app.include_router(golden.router, prefix="/api/golden", tags=["golden"])
    app.include_router(cohort.router, prefix="/api/cohort", tags=["cohort"])
    app.include_router(narrative.router, prefix="/api/narrative", tags=["narrative"])
    app.include_router(budget.router, prefix="/api/budget", tags=["budget"])
    app.include_router(incident.router, prefix="/api/incident", tags=["incident"])
    app.include_router(capabilities.router, prefix="/api/capabilities", tags=["capabilities"])
    app.include_router(scenario_bank.router, prefix="/api/scenario-bank", tags=["scenario-bank"])
    app.include_router(locales.router, prefix="/api/locales", tags=["locales"])

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        from src.telemetry.metrics import render_latest

        body, content_type = render_latest()
        return Response(content=body, media_type=content_type)

    # Auto-instrument request handling for distributed tracing (no-op unless activated; ADR-0031).
    configure_tracing()
    instrument_app(app)

    return app


app = create_app()
