"""Integration tests for metrics exposition + dashboard aggregates."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
MEDLINK = str(REPO_ROOT / "packs" / "medlink-pro" / "v1")


async def test_metrics_endpoint_exposes_prometheus(client: AsyncClient) -> None:
    # A run increments simforge_runs_total.
    await client.post("/api/packs/", json={"pack_dir": MEDLINK})
    await client.post("/api/scenarios/scn.ml.place.002/run")

    resp = await client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "simforge_runs_total" in body
    assert "simforge_readiness_gate_total" in body


async def test_dashboard_summary(client: AsyncClient) -> None:
    resp = await client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert "agents" in body and "active_certs" in body
    assert body["agents"] >= 3


async def test_dashboard_throughput(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": MEDLINK})
    await client.post("/api/scenarios/scn.ml.place.002/run")
    resp = await client.get("/api/dashboard/throughput")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_runs"] >= 1
    assert body["total_tokens"] > 0


async def test_dashboard_readiness_matrix(client: AsyncClient) -> None:
    resp = await client.get("/api/dashboard/readiness-matrix")
    assert resp.status_code == 200
    assert "forge_caps" in resp.json()
