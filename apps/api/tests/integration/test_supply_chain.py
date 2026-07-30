"""Supply-Chain & Third-Party Dependency Governance (v1.2): SBOM from repo manifests + flags."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.config import settings
from src.services.supply_chain.sbom import _read_manifests, generate_sbom


async def test_sbom_lists_real_dependencies(client: AsyncClient) -> None:
    res = (await client.get("/api/supply-chain/sbom")).json()
    assert res["generated"] is True
    names = {c["name"] for c in res["components"]}
    # Real runtime deps from apps/api/pyproject.toml + apps/web/package.json.
    assert "fastapi" in names
    assert "next" in names
    assert res["counts"]["total"] == len(res["components"])


async def test_unpinned_python_dep_flagged() -> None:
    _read_manifests.cache_clear()
    sbom = generate_sbom()
    fastapi = next(c for c in sbom["components"] if c["name"] == "fastapi")
    # pyproject uses fastapi>=0.110 — a range, not an exact pin.
    assert fastapi["pinned"] is False
    assert "unpinned" in fastapi["flags"]


async def test_pinned_npm_dep_not_flagged() -> None:
    _read_manifests.cache_clear()
    sbom = generate_sbom()
    react = next(c for c in sbom["components"] if c["name"] == "react")
    # package.json pins react to an exact 18.3.1.
    assert react["pinned"] is True
    assert "unpinned" not in react["flags"]


async def test_denylist_flags_component(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "supply_chain_denylist", "fastapi, left-pad")
    _read_manifests.cache_clear()
    sbom = generate_sbom()
    fastapi = next(c for c in sbom["components"] if c["name"] == "fastapi")
    assert "denylisted" in fastapi["flags"]
    assert sbom["counts"]["denylisted"] >= 1


async def test_no_vuln_feed_by_default(client: AsyncClient) -> None:
    res = (await client.get("/api/supply-chain/sbom")).json()
    assert res["vuln_feed_configured"] is False
