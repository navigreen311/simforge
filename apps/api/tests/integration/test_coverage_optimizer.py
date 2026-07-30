"""Scenario Coverage Optimizer (v1.2): ranked authoring worklist from the coverage heatmap."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.pack import Scenario

_N = [0]


def _seed(session: AsyncSession, *, role: str, tier: str, n: int) -> None:
    for _ in range(n):
        _N[0] += 1
        session.add(
            Scenario(
                scenarioId=f"scn.{_N[0]:04d}",
                packId="pk-x",
                title="t",
                tier=tier,
                testedAgentVillageId=role,
                yamlPath="p.yml",
                yamlHash="h",
                sloSeconds=60,
                isGolden=False,
            )
        )


async def test_ranks_crisis_gaps_above_foundational(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Role A: foundational fully covered, crisis empty. Role B: crisis has 2 (thin).
    _seed(db_session, role="agent_a", tier="foundational", n=3)
    _seed(db_session, role="agent_b", tier="advanced_crisis", n=2)
    await db_session.commit()

    rep = (await client.get("/api/coverage/recommendations")).json()
    assert rep["fully_covered"] is False
    assert rep["total_deficit"] > 0
    recs = rep["recommendations"]
    # The empty crisis cell for agent_a should rank first (deficit 3 × weight 3 × empty bonus).
    top = recs[0]
    assert top["role"] == "agent_a"
    assert top["tier"] == "advanced_crisis"
    assert top["current"] == 0 and top["deficit"] == 3
    # An empty crisis cell outranks agent_b's thin (2/3) crisis cell.
    b_crisis = next(r for r in recs if r["role"] == "agent_b" and r["tier"] == "advanced_crisis")
    assert top["priority"] > b_crisis["priority"]


async def test_fully_covered_when_all_cells_meet_min(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    for tier in ("foundational", "intermediate", "advanced_crisis"):
        _seed(db_session, role="solo", tier=tier, n=3)
    await db_session.commit()
    rep = (await client.get("/api/coverage/recommendations")).json()
    assert rep["fully_covered"] is True
    assert rep["recommendations"] == []


async def test_min_per_cell_param(client: AsyncClient, db_session: AsyncSession) -> None:
    _seed(db_session, role="r", tier="foundational", n=3)
    await db_session.commit()
    # With min=3 the cell is covered; with min=5 it needs 2 more.
    covered = (await client.get("/api/coverage/recommendations?min_per_cell=3")).json()
    assert all(
        rec["role"] != "r" or rec["tier"] != "foundational" for rec in covered["recommendations"]
    )
    stricter = (await client.get("/api/coverage/recommendations?min_per_cell=5")).json()
    rec = next(
        r for r in stricter["recommendations"] if r["role"] == "r" and r["tier"] == "foundational"
    )
    assert rec["deficit"] == 2 and rec["target"] == 5
