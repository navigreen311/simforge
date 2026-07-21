"""Integration: a PEP enforcing PDP decisions over HTTP against the running app (ADR-0024)."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

from src.services.governance.pdp import AuthRequest
from src.services.pep import HttpDecisionSource, Pep

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")
FORGE_CAP = "cre-forge.call_center.outbound_seller_outreach"


async def _issue_cert(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    run = (await client.post("/api/scenarios/scn.gs.src.001/run")).json()
    r = await client.post(
        "/api/certs/agent/issue",
        json={
            "agent_village_id": "david_kim",
            "forge_cap": FORGE_CAP,
            "tier": "foundational",
            "battery_run_ids": [run["run_id"]],
            "approver_id": "ivan",
            "pack_id": "pack.greenstone.v1",
        },
    )
    assert r.status_code == 200, r.text


def _pep(client: AsyncClient) -> Pep:
    # Route the PEP's HTTP source at the in-process app via the client's ASGI transport.
    source = HttpDecisionSource("http://test", transport=client._transport)  # noqa: SLF001
    return Pep(source)


async def test_pep_enforces_and_caches_over_http(client: AsyncClient) -> None:
    await _issue_cert(client)  # david_kim → L2
    pep = _pep(client)

    d1 = await pep.authorize(AuthRequest(subject_agent_id="david_kim", action=FORGE_CAP))
    assert d1.decision == "downgrade_and_retry" and d1.reason_code == "draft_only_l2"

    # Second call is served from the PEP cache (no second PDP round-trip).
    d2 = await pep.authorize(AuthRequest(subject_agent_id="david_kim", action=FORGE_CAP))
    assert d2.decision == "downgrade_and_retry"
    assert pep.cache_hit_ratio() == 0.5
    assert pep.stats()["entries"] == 1


async def test_pep_denies_uncertified_over_http(client: AsyncClient) -> None:
    pep = _pep(client)
    d = await pep.authorize(AuthRequest(subject_agent_id="david_kim", action=FORGE_CAP))
    assert d.decision == "deny" and d.reason_code == "no_certification"
    assert d.fail_policy == "fail_closed"


async def test_pep_invalidation_forces_refetch(client: AsyncClient) -> None:
    await _issue_cert(client)
    pep = _pep(client)
    await pep.authorize(AuthRequest(subject_agent_id="david_kim", action=FORGE_CAP))
    # Simulate a revocation event arriving on the channel → drop the cached decision.
    assert pep.invalidate("david_kim", FORGE_CAP) == 1
    await pep.authorize(AuthRequest(subject_agent_id="david_kim", action=FORGE_CAP))
    assert pep.stats()["misses"] == 2  # both were live PDP round-trips
