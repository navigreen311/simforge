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


# ── Add agents (single + bulk) ──────────────────────────────────────────────


async def _eng_dept_id(client: AsyncClient) -> str:
    depts = (await client.get("/api/departments/")).json()["items"]
    return next(d["id"] for d in depts if d["villageKey"] == "Engineering")


async def test_add_single_agent_starts_at_floor(client: AsyncClient) -> None:
    dept = await _eng_dept_id(client)
    r = await client.post(
        "/api/agents/", json={"name": "Ada Byron", "role": "Analyst", "departmentId": dept}
    )
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["villageAgentId"] == "ada_byron"  # auto-slugged
    assert a["currentAutonomyLevel"] == "L1"  # floor — never a backdoor around certification
    assert a["gardnerFlag"] is False


async def test_add_single_rejects_bad_input(client: AsyncClient) -> None:
    bad = await client.post("/api/agents/", json={"name": "", "departmentId": "x"})
    assert bad.status_code == 400
    dept = await _eng_dept_id(client)
    # duplicate id
    await client.post("/api/agents/", json={"name": "Dup One", "departmentId": dept})
    r = await client.post(
        "/api/agents/", json={"name": "Dup Two", "villageAgentId": "dup_one", "departmentId": dept}
    )
    assert r.status_code == 400 and "already exists" in r.json()["detail"]
    # unknown department
    r2 = await client.post("/api/agents/", json={"name": "No Dept", "departmentId": "nope"})
    assert r2.status_code == 400


async def test_bulk_import_validates_per_row(client: AsyncClient) -> None:
    # existing id to trigger a duplicate-skip
    eng = await _eng_dept_id(client)
    await client.post(
        "/api/agents/",
        json={"name": "Grace Hopper", "villageAgentId": "grace_hopper", "departmentId": eng},
    )
    rows = [
        {"name": "Alan Turing", "role": "Engineer", "department": "Engineering", "flags": "l10"},
        {"name": "", "department": "Engineering"},  # missing name → error
        {"name": "Bad Dept", "department": "Nonexistent"},  # unknown dept → error
        {"name": "Grace Hopper", "id": "grace_hopper", "department": "Engineering"},  # dup → skip
        {"name": "Dupe In Batch", "id": "dib", "department": "Recruitment"},
        {"name": "Dupe In Batch 2", "id": "dib", "department": "Recruitment"},  # dup within batch
    ]
    r = await client.post("/api/agents/bulk", json={"rows": rows})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["imported"] == 2  # Alan Turing + first "dib"
    assert b["errored"] == 2  # missing name + unknown dept
    assert b["skipped"] == 2  # existing grace_hopper + dup-in-batch dib
    # imported agents start at floor with the parsed flag
    turing = (await client.get("/api/agents/alan_turing")).json()
    assert turing["currentAutonomyLevel"] == "L1"
    assert turing["level10Enabled"] is True  # parsed from flags "l10" — but NOT autonomy
    # invalid rows were NOT invented
    assert (await client.get("/api/agents/bad_dept")).status_code == 404
