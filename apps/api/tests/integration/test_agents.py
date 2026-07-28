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


async def test_agents_legend(client: AsyncClient) -> None:
    body = (await client.get("/api/agents/legend")).json()
    assert body["floor"] == "L1"
    levels = {lv["level"]: lv for lv in body["levels"]}
    assert set(levels) == {"L1", "L2", "L3", "L4", "L5"}
    assert levels["L1"]["is_floor"] is True
    assert "Observe" in levels["L1"]["meaning"]
    assert levels["L5"]["is_floor"] is False
    flags = {f["key"]: f for f in body["flags"]}
    assert set(flags) == {"gardner", "l10"}
    # neither flag has a formal in-app definition — reported, not fabricated
    assert flags["gardner"]["defined"] is False
    assert flags["l10"]["defined"] is False
