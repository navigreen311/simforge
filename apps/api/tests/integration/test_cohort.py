"""Cognitive-drift canary + cohort analytics (ADR-0034)."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")


async def test_daily_canary_captures_and_is_idempotent(client: AsyncClient) -> None:
    first = await client.post("/api/cohort/snapshots")
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["captured"] >= 1
    agents = {a["agent"] for a in body["agents"]}
    assert "david_kim" in agents

    # Re-running the same day is idempotent: still one snapshot per agent, baseline delta = 0.
    second = await client.post("/api/cohort/snapshots")
    assert second.status_code == 200

    hist = await client.get("/api/cohort/agent/david_kim/cognitive-history")
    assert hist.status_code == 200
    snaps = hist.json()["snapshots"]
    assert len(snaps) == 1  # idempotent per (agent, day)
    # First-ever snapshot is its own baseline → zero drift.
    assert snaps[0]["drift_magnitude"] == 0.0
    assert "fot.pressure" in snaps[0]["values"]


async def test_cognitive_history_unknown_agent_404(client: AsyncClient) -> None:
    resp = await client.get("/api/cohort/agent/nobody/cognitive-history")
    assert resp.status_code == 404


async def test_cohort_analytics_heatmap(client: AsyncClient) -> None:
    # Seed some scored runs so cognitive dims are populated for the cohort.
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    await client.post("/api/scenarios/scn.gs.src.001/run")
    await client.post("/api/scenarios/scn.gs.buy.002/run")

    resp = await client.get("/api/cohort/department/Engineering/analytics")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["department"] == "Engineering"
    assert "cognitive_aggregate" in body["dimensions"]

    dk = next((a for a in body["agents"] if a["agent"] == "david_kim"), None)
    assert dk is not None
    assert dk["runs"] >= 2
    assert dk["dims"]["cognitive_aggregate"] is not None
    assert 0.0 <= dk["aggregate_percentile"] <= 1.0


async def test_cohort_analytics_unknown_department_404(client: AsyncClient) -> None:
    resp = await client.get("/api/cohort/department/Nonexistent/analytics")
    assert resp.status_code == 404


async def test_snapshot_status_reports_drift_availability(client: AsyncClient) -> None:
    # With no snapshots captured, drift is not available (needs >= 2 dates) — reported honestly.
    body = (await client.get("/api/cohort/snapshots/status")).json()
    assert body["snapshot_dates"] == 0
    assert body["total_snapshots"] == 0
    assert body["drift_available"] is False
    assert body["latest_date"] is None
