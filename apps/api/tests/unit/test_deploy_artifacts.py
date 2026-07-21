"""Deploy artifacts are well-formed — compose parses, Dockerfile is production-shaped (ADR-0030)."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE = REPO_ROOT / "infra" / "compose" / "docker-compose.full.yml"
PROM = REPO_ROOT / "infra" / "compose" / "prometheus.yml"
DOCKERFILE = REPO_ROOT / "apps" / "api" / "Dockerfile"


def test_full_stack_compose_is_valid_and_complete() -> None:
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    services = compose["services"]
    assert {"api", "postgres", "redis", "prometheus", "grafana"} <= set(services)
    # The API builds from the Dockerfile and depends on healthy datastores.
    assert services["api"]["build"]["dockerfile"] == "apps/api/Dockerfile"
    assert "postgres" in services["api"]["depends_on"]
    # Grafana mounts the provisioning + dashboards we ship (ADR-0029).
    vols = services["grafana"]["volumes"]
    assert any("grafana/provisioning" in v for v in vols)
    assert any("grafana/dashboards" in v for v in vols)


def test_prometheus_scrapes_the_api() -> None:
    prom = yaml.safe_load(PROM.read_text(encoding="utf-8"))
    jobs = {j["job_name"]: j for j in prom["scrape_configs"]}
    assert "simforge-api" in jobs
    assert jobs["simforge-api"]["metrics_path"] == "/metrics"
    assert "api:8000" in jobs["simforge-api"]["static_configs"][0]["targets"]


def test_dockerfile_is_production_shaped() -> None:
    df = DOCKERFILE.read_text(encoding="utf-8")
    assert "FROM python:3.12-slim AS runtime" in df
    assert "USER simforge" in df  # non-root
    assert "HEALTHCHECK" in df  # container health
    assert "uvicorn" in df and "src.main:app" in df
    assert "packages/validator" in df  # the runtime dependency is installed
