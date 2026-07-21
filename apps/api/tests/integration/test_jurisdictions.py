"""Integration tests for the Jurisdiction Engine router (ADR-0019)."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
MEDLINK = str(REPO_ROOT / "packs" / "medlink-pro" / "v1")


async def test_list_jurisdictions(client: AsyncClient) -> None:
    resp = await client.get("/api/jurisdictions/")
    assert resp.status_code == 200
    codes = {j["code"] for j in resp.json()["jurisdictions"]}
    assert {"US-FED", "US-NV", "US-CA", "US-TX"} <= codes


async def test_california_requirements(client: AsyncClient) -> None:
    resp = await client.get("/api/jurisdictions/US-CA/requirements", params={"phi_required": True})
    req = set(resp.json()["required_flags"])
    assert {"oig_sam", "i9", "hipaa", "cdph_ca", "ccpa"} <= req


async def test_unknown_jurisdiction_404(client: AsyncClient) -> None:
    resp = await client.get("/api/jurisdictions/US-ZZ/requirements")
    assert resp.status_code == 404


async def test_coverage_reports_missing(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/jurisdictions/coverage",
        json={"declared_flags": ["hcqc_nv"], "phi_required": True},
    )
    body = resp.json()
    assert body["satisfied"] is False
    assert set(body["missing_flags"]) == {"oig_sam", "i9", "hipaa"}
    assert body["jurisdictions"] == ["US-FED", "US-NV"]  # inferred from the flag


async def test_pack_coverage_medlink_satisfied(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": MEDLINK})
    resp = await client.get("/api/jurisdictions/coverage/pack/pack.medlink-pro.v1")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # medlink-pro declares hcqc_nv + hipaa + oig_sam + i9 → NV + federal fully covered.
    assert body["satisfied"] is True
    assert "US-NV" in body["jurisdictions"]
