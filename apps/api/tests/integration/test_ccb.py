"""Integration tests for CCB capture/latest endpoints and fingerprint capture."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.village.fingerprint import capture_fingerprint
from src.services.village.reader import VillageReader


async def test_capture_then_latest_ccb(client: AsyncClient) -> None:
    # No CCB yet
    resp = await client.get("/api/agents/taylor_zhang/ccb/latest")
    assert resp.status_code == 404

    # Capture
    cap = await client.post("/api/agents/taylor_zhang/ccb/capture", json={"phase": "pre"})
    assert cap.status_code == 200
    body = cap.json()
    assert body["agent_village_id"] == "taylor_zhang"
    assert body["phase"] == "pre"
    assert len(body["content_hash"]) == 64
    assert set(body["frameworks"].keys()) == {
        "game",
        "mate",
        "soul",
        "breath",
        "fot",
        "hfm",
        "arc",
        "echo",
        "drift",
        "ame",
    }

    # Latest now returns it
    latest = await client.get("/api/agents/taylor_zhang/ccb/latest")
    assert latest.status_code == 200
    assert latest.json()["snapshot_id"] == body["snapshot_id"]


async def test_capture_unknown_agent_404(client: AsyncClient) -> None:
    resp = await client.post("/api/agents/ghost/ccb/capture", json={"phase": "pre"})
    assert resp.status_code == 404


async def test_fingerprint_capture_records_current(
    db_session: AsyncSession, village_reader: VillageReader
) -> None:
    first = await capture_fingerprint(db_session, village_reader)
    assert first.newly_recorded is True
    assert first.drift_detected is False
    assert len(first.fingerprint) == 64

    # Re-capturing the same tree = no new record, no drift
    second = await capture_fingerprint(db_session, village_reader)
    assert second.newly_recorded is False
    assert second.drift_detected is False
    assert second.fingerprint == first.fingerprint
