"""Integration tests for agents + departments routers."""

from __future__ import annotations

from httpx import AsyncClient


async def test_list_agents(client: AsyncClient) -> None:
    resp = await client.get("/api/agents/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4
    ids = {a["villageAgentId"] for a in body["items"]}
    assert {"taylor_zhang", "gardner", "jennifer_adams", "david_kim"} <= ids


async def test_list_agents_filter_by_autonomy(client: AsyncClient) -> None:
    resp = await client.get("/api/agents/", params={"autonomy_level": "L1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert all(a["currentAutonomyLevel"] == "L1" for a in body["items"])


async def test_get_agent_detail(client: AsyncClient) -> None:
    resp = await client.get("/api/agents/gardner")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Gardner"
    assert body["gardnerFlag"] is True
    assert body["level10Enabled"] is True


async def test_get_agent_404(client: AsyncClient) -> None:
    resp = await client.get("/api/agents/nonexistent")
    assert resp.status_code == 404


async def test_list_departments(client: AsyncClient) -> None:
    resp = await client.get("/api/departments/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    keys = {d["villageKey"] for d in body["items"]}
    assert {"Engineering", "Recruitment"} == keys


async def test_get_department_detail(client: AsyncClient) -> None:
    resp = await client.get("/api/departments/Engineering")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Engineering"
