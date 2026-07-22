"""Locale registry + pack locale surfacing (ADR-0041)."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")


async def test_locales_endpoint_reports_coverage(client: AsyncClient) -> None:
    resp = await client.get("/api/locales/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["default"] == "en"
    assert set(body["locales"]) == {"en", "es"}
    assert body["prompt_coverage"]["p7_cx"] == ["en", "es"]


async def test_pack_locale_defaults_to_en(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    packs = (await client.get("/api/packs/")).json()["items"]
    greenstone = next(p for p in packs if p["packId"] == "pack.greenstone.v1")
    assert greenstone["locale"] == "en"  # existing packs unchanged → scores stable
