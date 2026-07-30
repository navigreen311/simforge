"""§10.4 dashboard data endpoints: coverage heatmap, dept×context, cognitive trends,
cert-lifecycle timeline, CCB pre/post diff."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.ccb import CCB
from src.models.cert import CertLifecycleEvent, DeptCert
from src.models.cognitive_snapshot import CognitiveSnapshot
from src.models.department import Department
from src.models.run import Run
from src.utils.time import utcnow

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")


async def test_coverage_heatmap_role_by_tier(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    res = (await client.get("/api/dashboard/coverage-heatmap")).json()
    assert res["axis"] == "tier"
    assert res["min_per_cell"] == 3
    assert res["cells"], "greenstone should produce coverage cells"
    for cell in res["cells"]:
        assert {"pack", "role", "tier", "count", "meets_min"} <= set(cell)


async def test_dept_context_matrix(client: AsyncClient, db_session: AsyncSession) -> None:
    dept = (
        await db_session.execute(select(Department).where(Department.villageKey == "Engineering"))
    ).scalar_one()
    db_session.add(
        DeptCert(
            departmentId=dept.id,
            forgeContext="capital-forge",
            tier="T2",
            status="active",
            issuedAt=utcnow(),
            expiresAt=utcnow(),
            certSnapshotId="cs-dept-1",
            prerequisiteAgentCertIds=["ac1", "ac2", "ac3"],
        )
    )
    await db_session.commit()
    res = (await client.get("/api/dashboard/dept-context-matrix")).json()
    assert res["total_dept_certs"] == 1
    assert "capital-forge" in res["forge_contexts"]
    cell = res["cells"][0]
    assert cell["department"] == "Engineering"
    assert cell["covering_certs"] == 3


async def test_cognitive_trends(client: AsyncClient, db_session: AsyncSession) -> None:
    agent = (
        await db_session.execute(select(Agent).where(Agent.villageAgentId == "taylor_zhang"))
    ).scalar_one()
    base = utcnow()
    for i, mag in enumerate((0.1, 0.2)):
        db_session.add(
            CognitiveSnapshot(
                agentId=agent.id,
                date=base - timedelta(days=1 - i),
                ccbSnapshotId=f"snap-{i}",
                values={"c3_composure": 0.8 - i * 0.1},
                deltas={"c3_composure": -0.1},
                driftMagnitude=mag,
            )
        )
    await db_session.commit()
    res = (await client.get("/api/dashboard/cognitive-trends/taylor_zhang")).json()
    assert res["agent"] == "taylor_zhang"
    assert len(res["points"]) == 2
    assert res["points"][0]["values"]["c3_composure"] == 0.8

    empty = (await client.get("/api/dashboard/cognitive-trends/nobody")).json()
    assert empty["points"] == []
    assert empty["has_trend"] is False


async def test_cert_timeline(client: AsyncClient, db_session: AsyncSession) -> None:
    db_session.add(
        CertLifecycleEvent(
            agentCertId="ac-1",
            event="issued",
            timestamp=utcnow(),
            actor="scheduler",
            reason="initial certification",
        )
    )
    await db_session.commit()
    res = (await client.get("/api/dashboard/cert-timeline")).json()
    assert len(res["events"]) == 1
    ev = res["events"][0]
    assert ev["event"] == "issued"
    assert ev["actor"] == "scheduler"


async def test_ccb_diff(client: AsyncClient, db_session: AsyncSession) -> None:
    pre = CCB(
        snapshotId="ccb-pre",
        agentVillageId="taylor_zhang",
        phase="pre",
        takenAt=utcnow(),
        contentHash="h1",
        game={"clarity": 0.9},
        mate={},
        soul={"identity": "stable"},
        breath={},
        fot={},
        hfm={},
        arc={},
        echo={},
        drift={},
        ame={},
        villageSchemaFingerprint="fp",
    )
    post = CCB(
        snapshotId="ccb-post",
        agentVillageId="taylor_zhang",
        phase="post",
        takenAt=utcnow(),
        contentHash="h2",
        game={"clarity": 0.6},
        mate={},
        soul={"identity": "stable"},
        breath={},
        fot={},
        hfm={},
        arc={},
        echo={},
        drift={},
        ame={},
        villageSchemaFingerprint="fp",
    )
    db_session.add_all([pre, post])
    await db_session.flush()
    run = Run(
        runId="run-ccb-1",
        scenarioId="scn-x",
        packId="pk-x",
        agentId="ag-x",
        executionMode="sandbox",
        narrativeMode="off",
        status="completed",
        startedAt=utcnow(),
        ccbPreId=pre.id,
        ccbPostId=post.id,
    )
    db_session.add(run)
    await db_session.commit()

    res = (await client.get("/api/dashboard/ccb-diff/run-ccb-1")).json()
    assert res["available"] is True
    assert res["identical"] is False
    game_diff = next(d for d in res["diffs"] if d["framework"] == "game")
    assert game_diff["changed_keys"] == ["clarity"]
    assert game_diff["before"]["clarity"] == 0.9
    assert game_diff["after"]["clarity"] == 0.6

    missing = (await client.get("/api/dashboard/ccb-diff/does-not-exist")).json()
    assert missing["available"] is False
