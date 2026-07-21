"""Unit tests for the health router."""

from __future__ import annotations

from httpx import AsyncClient


async def test_liveness(client: AsyncClient) -> None:
    resp = await client.get("/api/health/")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_readiness_reports_database_ok(client: AsyncClient) -> None:
    resp = await client.get("/api/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["checks"]["database"] == "ok"
    assert body["status"] in {"ok", "degraded"}


async def test_village_fingerprint(client: AsyncClient) -> None:
    resp = await client.get("/api/health/village-fingerprint")
    assert resp.status_code == 200
    body = resp.json()
    assert "fingerprint" in body
    assert body["drift_detected"] is False
