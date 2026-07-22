"""Golden Benchmark regression guard (ADR-0033).

Runs the golden suite against the committed baseline. A failure here means the evaluator (a rubric
scorer or gate threshold) changed a golden scenario's outcome/gate/dimension beyond tolerance — i.e.
a regression. If the change was intentional, regenerate via scripts/golden-baseline.py and review.
"""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")


async def _ingest_greenstone(client: AsyncClient) -> None:
    resp = await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    assert resp.status_code == 200, resp.text


async def test_golden_scenarios_listed(client: AsyncClient) -> None:
    await _ingest_greenstone(client)
    resp = await client.get("/api/golden/scenarios")
    assert resp.status_code == 200
    ids = {s["scenario_id"] for s in resp.json()["scenarios"]}
    assert ids == {"scn.gs.src.001", "scn.gs.buy.002", "scn.gs.crisis.003"}


async def test_golden_suite_no_regression(client: AsyncClient) -> None:
    """The core guard: the golden suite reproduces the committed baseline exactly."""
    await _ingest_greenstone(client)
    resp = await client.post("/api/golden/run")
    assert resp.status_code == 200, resp.text
    report = resp.json()

    assert report["total"] == 3
    assert report["regressions"] == 0, [r for r in report["results"] if r["status"] != "match"]
    assert report["passed"] is True
    assert all(r["status"] == "match" for r in report["results"])


async def test_golden_baseline_endpoint(client: AsyncClient) -> None:
    resp = await client.get("/api/golden/baseline")
    assert resp.status_code == 200
    baseline = resp.json()
    assert "scn.gs.src.001" in baseline["scenarios"]
    assert baseline["provider"] == "stub"
