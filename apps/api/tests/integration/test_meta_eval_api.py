"""Integration: the meta-eval report over real run scorecards (ADR-0027)."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")


async def test_meta_eval_report_over_real_scorecards(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    # Two runs → two scorecards to analyze.
    await client.post("/api/scenarios/scn.gs.src.001/run")
    await client.post("/api/scenarios/scn.gs.buy.002/run")

    report = (await client.get("/api/meta-eval/report")).json()
    assert report["n_scorecards"] >= 2
    labels = {d["dim"] for d in report["dimensions"]}
    assert {"p7_cx", "c1_breath", "cognitive_aggregate"} <= labels
    # Every dim has the expected shape.
    for d in report["dimensions"]:
        assert {"dim", "n", "mean", "stddev", "flags"} <= set(d)


async def test_meta_eval_scoped_to_pack(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    await client.post("/api/scenarios/scn.gs.src.001/run")
    report = (
        await client.get("/api/meta-eval/report", params={"pack_id": "pack.greenstone.v1"})
    ).json()
    assert report["pack_id"] == "pack.greenstone.v1"
    assert report["n_scorecards"] >= 1
