"""P0 UI-support endpoints + filter query params (UI audit PR).

Covers the new dashboard/health endpoints and the backward-compatible filter params added to the
runs / agents / certs list endpoints.
"""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")


async def _seed_runs(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    await client.post("/api/scenarios/scn.gs.src.001/run")  # foundational, david_kim
    await client.post("/api/scenarios/scn.gs.buy.002/run")  # intermediate, david_kim


# ---- health ----
async def test_llm_mode_reports_stub(client: AsyncClient) -> None:
    body = (await client.get("/api/health/llm-mode")).json()
    assert body["judge_provider"] == "stub"
    assert body["stub_scores"] is True


async def test_system_status(client: AsyncClient) -> None:
    body = (await client.get("/api/health/system-status")).json()
    assert body["hsm_status"] == "stub"
    assert "village_fingerprint" in body
    assert "constitution_version" in body


# ---- dashboard: integrity warnings ----
async def test_integrity_warning_fires_for_autonomy_without_certs(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Put david_kim at L4 with zero active certs — the exact contradiction the check must catch.
    await db_session.execute(
        update(Agent).where(Agent.villageAgentId == "david_kim").values(currentAutonomyLevel="L4")
    )
    await db_session.commit()

    body = (await client.get("/api/dashboard/integrity-warnings")).json()
    warned = {w["agent_id"] for w in body["warnings"]}
    assert "david_kim" in warned
    dk = next(w for w in body["warnings"] if w["agent_id"] == "david_kim")
    assert dk["warning_type"] == "autonomy_without_certs"
    assert dk["autonomy_level"] == "L4"
    assert dk["active_certs"] == 0

    # An L1 agent (taylor_zhang) must NOT be flagged.
    assert "taylor_zhang" not in warned


# ---- dashboard: runs-per-day + agent-certs ----
async def test_runs_per_day_is_zero_filled(client: AsyncClient) -> None:
    await _seed_runs(client)
    body = (await client.get("/api/dashboard/runs-per-day?days=14")).json()
    assert body["days"] == 14
    assert len(body["series"]) == 14
    assert sum(p["count"] for p in body["series"]) == 2  # two runs, today


async def test_agent_certs_summary(client: AsyncClient) -> None:
    body = (await client.get("/api/dashboard/agent-certs")).json()
    dk = next(i for i in body["items"] if i["agent_village_id"] == "david_kim")
    assert dk["active_certs"] == 0
    assert dk["total_certs"] == 0


# ---- runs filters + counts + pagination ----
async def test_runs_filters_and_counts(client: AsyncClient) -> None:
    await _seed_runs(client)

    counts = (await client.get("/api/runs/counts")).json()
    assert counts["total"] == 2

    # tier filter: only the foundational run
    foundational = (await client.get("/api/runs/?tier=foundational")).json()
    assert foundational["total"] == 1
    assert foundational["items"][0]["scenario_id"] == "scn.gs.src.001"

    # agent filter
    dk = (await client.get("/api/runs/?agent=david_kim")).json()
    assert dk["total"] == 2

    # execution mode (all sandbox by default)
    assert (await client.get("/api/runs/?execution_mode=sandbox")).json()["total"] == 2
    assert (await client.get("/api/runs/?execution_mode=integrated")).json()["total"] == 0

    # pagination: offset past the end → empty page, but total preserved
    page2 = (await client.get("/api/runs/?limit=1&offset=5")).json()
    assert page2["total"] == 2
    assert page2["items"] == []


# ---- agents filters ----
async def test_agents_search_and_cert_filter(client: AsyncClient) -> None:
    david = (await client.get("/api/agents/?search=david")).json()
    assert {a["villageAgentId"] for a in david["items"]} == {"david_kim"}

    # nobody has active certs in a fresh DB
    assert (await client.get("/api/agents/?has_active_certs=true")).json()["total"] == 0
    assert (await client.get("/api/agents/?has_active_certs=false")).json()["total"] >= 4

    # gardner flag filter
    gardner = (await client.get("/api/agents/?gardner_flag=true")).json()
    assert {a["villageAgentId"] for a in gardner["items"]} == {"gardner"}


# ---- certs filters ----
async def test_certs_filters(client: AsyncClient, db_session: AsyncSession) -> None:
    # Seed one active cert directly for david_kim.
    from datetime import timedelta

    from src.models.cert import AgentCert
    from src.utils.time import utcnow

    agent = (
        await db_session.execute(select(Agent).where(Agent.villageAgentId == "david_kim"))
    ).scalar_one()
    db_session.add(
        AgentCert(
            agentId=agent.id,
            forgeCap="cre-forge.call_center.outbound",
            tier="foundational",
            status="active",
            issuedAt=utcnow(),
            expiresAt=utcnow() + timedelta(days=90),
            certSnapshotId="snap-x",
        )
    )
    await db_session.commit()

    assert (await client.get("/api/certs/agent?status=active")).json()["total"] == 1
    assert (await client.get("/api/certs/agent?tier=foundational")).json()["total"] == 1
    assert (await client.get("/api/certs/agent?forge=cre-forge")).json()["total"] == 1
    assert (await client.get("/api/certs/agent?forge=capitalforge")).json()["total"] == 0
    assert (await client.get("/api/certs/agent?agent=david_kim")).json()["total"] == 1
