"""Mock-service depth (Wave 5): ledger, decision tiers, velocity, and uniform world-state."""

from __future__ import annotations

from httpx import AsyncClient

from src.services.forges.base import Fault, FaultType
from src.services.forges.capitalforge import LocalCapitalForgeAdapter
from src.services.forges.cre_forge import LocalCREForgeAdapter


async def test_bank_ledger_tracks_running_balance() -> None:
    a = LocalCapitalForgeAdapter()
    t = await a.provision_sandbox_tenant("depth")
    await a.apply(t.tenant_id, 40_000.0)
    await a.wire(t.tenant_id, 100_000.0)
    await a.emd_release(t.tenant_id, 10_000.0)
    world = await a.world_state(t.tenant_id)
    bank = world["bank"]
    # opening 250k, one 100k wire settled out.
    assert bank["opening_balance"] == 250_000.0
    assert bank["balance"] == 150_000.0
    assert bank["settled_out"] == 100_000.0
    assert bank["wire_count"] == 1
    assert len(bank["ledger"]) == 3
    assert bank["ledger"][-1]["op"] == "emd_release"
    assert [e["seq"] for e in bank["ledger"]] == [1, 2, 3]


async def test_apply_carries_decision_tier() -> None:
    a = LocalCapitalForgeAdapter()
    t = await a.provision_sandbox_tenant("depth")
    small = await a.apply(t.tenant_id, 20_000.0)
    assert small["outcome"] == "approved"
    assert small["decision"]["tier"] == "auto_approve"
    big = await a.apply(t.tenant_id, 999_000.0)
    assert big["decision"]["tier"] == "manual_review"


async def test_velocity_flag_trips_after_threshold() -> None:
    a = LocalCapitalForgeAdapter()
    t = await a.provision_sandbox_tenant("depth")
    for _ in range(3):
        await a.wire(t.tenant_id, 1_000.0)
    world = await a.world_state(t.tenant_id)
    assert world["bank"]["wire_count"] == 3
    assert world["bank"]["velocity_flag"] is True


async def test_declined_outcome_unchanged_by_depth() -> None:
    # Depth is additive — the pinned fault outcome/shape is preserved.
    a = LocalCapitalForgeAdapter()
    t = await a.provision_sandbox_tenant("depth")
    await a.inject_fault(t.tenant_id, Fault(FaultType.DECLINATION, "P1", "x", "bank"))
    res = await a.apply(t.tenant_id, 50_000.0)
    assert res["outcome"] == "declined"
    assert res["fault"]["type"] == "declination"


async def test_deal_desk_world_state() -> None:
    a = LocalCREForgeAdapter()
    t = await a.provision_sandbox_tenant("depth")
    await a.create_and_process(t.tenant_id, "assignment")
    await a.create_and_process(t.tenant_id, "wholesale", FaultType.TITLE_DEFECT)
    world = await a.world_state(t.tenant_id)
    dd = world["deal_desk"]
    assert dd["deal_count"] == 2
    assert dd["faulted_deals"] == 1
    assert dd["deals_by_type"]["assignment"] == 1


async def test_uniform_world_state_via_demo(client: AsyncClient) -> None:
    # Every demo endpoint now returns a structured world snapshot derived from the audit log.
    res = (await client.post("/api/forges/voiceforge/demo", json={"fault": "dropped_call"})).json()
    world = res["world"]
    assert world["forge"] == "voiceforge"
    assert world["audit_entries"] >= 1
    assert "dropped_call" in world["injected_faults"]
    assert res["result"]["outcome"] == "fault_detected"  # outcome preserved


async def test_capitalforge_demo_world_has_bank(client: AsyncClient) -> None:
    res = (await client.post("/api/forges/capitalforge/demo", json={"amount": 30_000.0})).json()
    assert "bank" in res["world"]
    assert res["world"]["bank"]["ledger"]
