"""Stakeholder Communication (v1.2): executive brief synthesized from live platform state."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.gap import SoftwareGap


def _p0_gap(session: AsyncSession) -> None:
    session.add(
        SoftwareGap(
            ticketId="SF-GAP-P0",
            runId="run-x",
            forge="capital-forge",
            module="ledger",
            severity="P0",
            summary="critical",
            detail="…",
            status="open",
            firstSeenRunId="run-x",
            lastSeenRunId="run-x",
        )
    )


async def test_green_when_clean(client: AsyncClient) -> None:
    brief = (await client.get("/api/stakeholder/brief")).json()
    # Fresh DB: no gaps, no unsafe forges → green.
    assert brief["tone"] == "green"
    assert brief["headline"] == "On track"
    assert "no blocking risks" in brief["recommended_actions"][0].lower()


async def test_red_on_p0_gap(client: AsyncClient, db_session: AsyncSession) -> None:
    _p0_gap(db_session)
    await db_session.commit()
    brief = (await client.get("/api/stakeholder/brief")).json()
    assert brief["tone"] == "red"
    assert brief["headline"] == "Attention needed"
    assert brief["metrics"]["open_gaps"]["P0"] == 1
    assert any("P0" in a for a in brief["recommended_actions"])


async def test_red_on_unsafe_forge(client: AsyncClient) -> None:
    await client.post("/api/parity/", json={"forge_cap": "vault-forge", "parity_score": 0.40})
    brief = (await client.get("/api/stakeholder/brief")).json()
    assert brief["tone"] == "red"
    assert "vault-forge" in brief["metrics"]["unsafe_forges"]
    assert any("parity" in a.lower() for a in brief["recommended_actions"])
