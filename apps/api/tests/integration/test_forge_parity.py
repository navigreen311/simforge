"""Sandbox-vs-production parity SLA (v1.1): record, derive unsafe_to_certify, optional enforce."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.services.cert.registry import CertIssuanceError, issue_agent_cert
from src.services.forge.parity import is_unsafe_to_certify


async def test_below_sla_marks_unsafe(client: AsyncClient) -> None:
    res = (
        await client.post(
            "/api/parity/",
            json={"forge_cap": "capital-forge", "parity_score": 0.72, "sample_size": 40},
        )
    ).json()
    assert res["unsafe_to_certify"] is True
    assert res["sla_threshold"] == 0.90

    ok = (
        await client.post(
            "/api/parity/",
            json={"forge_cap": "vault-forge", "parity_score": 0.97},
        )
    ).json()
    assert ok["unsafe_to_certify"] is False


async def test_summary_reports_latest_only(client: AsyncClient) -> None:
    await client.post("/api/parity/", json={"forge_cap": "cf", "parity_score": 0.50})
    await client.post("/api/parity/", json={"forge_cap": "cf", "parity_score": 0.95})
    summary = (await client.get("/api/parity/")).json()
    cf = [f for f in summary["forges"] if f["forge_cap"] == "cf"]
    assert len(cf) == 1
    assert cf[0]["parity_score"] == 0.95  # latest wins
    assert cf[0]["unsafe_to_certify"] is False


async def test_unmeasured_forge_is_safe(client: AsyncClient, db_session: AsyncSession) -> None:
    assert await is_unsafe_to_certify(db_session, "never-measured") is False
    res = (await client.get("/api/parity/never-measured")).json()
    assert res["measured"] is False
    assert res["unsafe_to_certify"] is False


async def test_enforcement_blocks_cert_issuance(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await client.post("/api/parity/", json={"forge_cap": "capital-forge", "parity_score": 0.60})
    monkeypatch.setattr(settings, "parity_enforce", True)
    with pytest.raises(CertIssuanceError, match="unsafe_to_certify"):
        await issue_agent_cert(
            db_session,
            agent_village_id="taylor_zhang",
            forge_cap="capital-forge",
            tier="foundational",
            battery_run_ids=[],
            approver_id="ivan",
            pack_id="pack.greenstone.v1",
        )


async def test_no_enforcement_by_default(client: AsyncClient, db_session: AsyncSession) -> None:
    # Below SLA, but enforcement off → issuance is not blocked by parity (it fails later on the
    # empty battery instead, proving the parity gate did NOT short-circuit).
    await client.post("/api/parity/", json={"forge_cap": "capital-forge", "parity_score": 0.10})
    assert settings.parity_enforce is False
    with pytest.raises(CertIssuanceError) as exc:
        await issue_agent_cert(
            db_session,
            agent_village_id="taylor_zhang",
            forge_cap="capital-forge",
            tier="foundational",
            battery_run_ids=[],
            approver_id="ivan",
            pack_id="pack.greenstone.v1",
        )
    assert "unsafe_to_certify" not in str(exc.value)
