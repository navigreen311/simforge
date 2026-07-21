"""Integration tests for the Forges router + Forge-fault → Software Gap loop."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")
MEDLINK = str(REPO_ROOT / "packs" / "medlink-pro" / "v1")


async def test_list_forges_and_health(client: AsyncClient) -> None:
    resp = await client.get("/api/forges/")
    assert resp.status_code == 200
    forges = {f["forge"]: f["ok"] for f in resp.json()["forges"]}
    # All six Forges are now real (Local adapters).
    assert all(
        forges[name]
        for name in ("capitalforge", "vaf", "voiceforge", "cre-forge", "medlink-pro", "funnelforge")
    )

    for name in ("capitalforge", "vaf", "voiceforge", "cre-forge", "medlink-pro", "funnelforge"):
        health = await client.get(f"/api/forges/{name}/health")
        assert health.json()["mode"] == "local"

    # An unknown forge name still reports unhealthy (Null adapter).
    assert (await client.get("/api/forges/nonexistent-forge/health")).json()["ok"] is False


async def test_capitalforge_demo_fault(client: AsyncClient) -> None:
    resp = await client.post("/api/forges/capitalforge/demo", json={"fault": "declination"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["outcome"] == "declined"
    assert body["result"]["fault"]["type"] == "declination"


async def test_vaf_demo_doc_fault(client: AsyncClient) -> None:
    resp = await client.post("/api/forges/vaf/demo", json={"fault": "forged_signature"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["outcome"] == "fault_detected"
    assert body["result"]["fault"]["type"] == "forged_signature"
    assert body["result"]["fault"]["severity"] == "P0"


async def test_voiceforge_demo_call_fault(client: AsyncClient) -> None:
    resp = await client.post("/api/forges/voiceforge/demo", json={"fault": "dropped_call"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["outcome"] == "fault_detected"
    assert body["result"]["fault"]["type"] == "dropped_call"
    assert body["result"]["fault"]["severity"] == "P0"


async def test_cre_forge_demo_deal_fault(client: AsyncClient) -> None:
    resp = await client.post("/api/forges/cre-forge/demo", json={"fault": "title_defect"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["outcome"] == "fault_detected"
    assert body["result"]["fault"]["type"] == "title_defect"
    assert body["result"]["fault"]["severity"] == "P0"


async def test_medlink_pro_demo_console_fault(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/forges/medlink-pro/demo",
        json={"fault": "credential_expired_unflagged", "module": "compliance"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["outcome"] == "fault_detected"
    assert body["result"]["fault"]["type"] == "credential_expired_unflagged"
    assert body["result"]["fault"]["severity"] == "P0"


async def test_funnelforge_demo_flow_fault(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/forges/funnelforge/demo", json={"fault": "webhook_dropped", "module": "leads"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["outcome"] == "fault_detected"
    assert body["result"]["fault"]["type"] == "webhook_dropped"
    assert body["result"]["fault"]["severity"] == "P0"


async def test_vaf_scenario_run_emits_forge_gap(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    # scn.gs.crisis.003 tests vaf.doc_vault.retrieve for david_kim; advanced_crisis tier → fault
    run = await client.post("/api/scenarios/scn.gs.crisis.003/run")
    assert run.status_code == 200, run.text

    trace = (await client.get(f"/api/runs/{run.json()['run_id']}/trace")).json()
    vaf_faults = [
        e
        for e in trace["events"]
        if e["event_type"] == "forge_fault" and e["payload"]["forge"] == "vaf"
    ]
    assert vaf_faults, "expected a VAF forge_fault trace event"

    gaps = (await client.get("/api/gaps/software", params={"forge": "vaf"})).json()
    assert gaps["total"] >= 1
    assert gaps["items"][0]["forge"] == "vaf"


async def test_voiceforge_scenario_run_emits_forge_gap(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    # scn.gs.crisis.003 also tests voiceforge.call_center.inbound; advanced_crisis tier → fault
    run = await client.post("/api/scenarios/scn.gs.crisis.003/run")
    assert run.status_code == 200, run.text

    trace = (await client.get(f"/api/runs/{run.json()['run_id']}/trace")).json()
    voice_faults = [
        e
        for e in trace["events"]
        if e["event_type"] == "forge_fault" and e["payload"]["forge"] == "voiceforge"
    ]
    assert voice_faults, "expected a VoiceForge forge_fault trace event"

    gaps = (await client.get("/api/gaps/software", params={"forge": "voiceforge"})).json()
    assert gaps["total"] >= 1
    assert gaps["items"][0]["forge"] == "voiceforge"


async def test_cre_forge_scenario_run_emits_forge_gap(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    # scn.gs.crisis.003 also tests cre-forge.deals.title; advanced_crisis tier → fault
    run = await client.post("/api/scenarios/scn.gs.crisis.003/run")
    assert run.status_code == 200, run.text

    trace = (await client.get(f"/api/runs/{run.json()['run_id']}/trace")).json()
    cre_faults = [
        e
        for e in trace["events"]
        if e["event_type"] == "forge_fault" and e["payload"]["forge"] == "cre-forge"
    ]
    assert cre_faults, "expected a CRE Forge forge_fault trace event"

    gaps = (await client.get("/api/gaps/software", params={"forge": "cre-forge"})).json()
    assert gaps["total"] >= 1
    assert gaps["items"][0]["forge"] == "cre-forge"


async def test_medlink_pro_scenario_run_emits_forge_gap(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": MEDLINK})
    # scn.ml.place.002 tests medlink-pro.scheduler.shift_fill for jennifer_adams (seeded),
    # seed 402 (even) → fault
    run = await client.post("/api/scenarios/scn.ml.place.002/run")
    assert run.status_code == 200, run.text

    trace = (await client.get(f"/api/runs/{run.json()['run_id']}/trace")).json()
    mlp_faults = [
        e
        for e in trace["events"]
        if e["event_type"] == "forge_fault" and e["payload"]["forge"] == "medlink-pro"
    ]
    assert mlp_faults, "expected a medlink-pro forge_fault trace event"

    gaps = (await client.get("/api/gaps/software", params={"forge": "medlink-pro"})).json()
    assert gaps["total"] >= 1
    assert gaps["items"][0]["forge"] == "medlink-pro"


async def test_funnelforge_scenario_run_emits_forge_gap(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": MEDLINK})
    # scn.ml.place.002 also tests funnelforge.sequences.trigger for jennifer_adams (seeded),
    # seed 402 (even) → fault
    run = await client.post("/api/scenarios/scn.ml.place.002/run")
    assert run.status_code == 200, run.text

    trace = (await client.get(f"/api/runs/{run.json()['run_id']}/trace")).json()
    ff_faults = [
        e
        for e in trace["events"]
        if e["event_type"] == "forge_fault" and e["payload"]["forge"] == "funnelforge"
    ]
    assert ff_faults, "expected a funnelforge forge_fault trace event"

    gaps = (await client.get("/api/gaps/software", params={"forge": "funnelforge"})).json()
    assert gaps["total"] >= 1
    assert gaps["items"][0]["forge"] == "funnelforge"


async def test_capitalforge_scenario_run_emits_forge_gap(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    # scn.gs.buy.002 tests capitalforge.emd.release for david_kim (seeded), seed 202 (even) → fault
    run = await client.post("/api/scenarios/scn.gs.buy.002/run")
    assert run.status_code == 200, run.text

    # The run's trace has a forge_fault event
    trace = (await client.get(f"/api/runs/{run.json()['run_id']}/trace")).json()
    assert any(e["event_type"] == "forge_fault" for e in trace["events"])

    # …which surfaced a real Software Gap against capitalforge
    gaps = (await client.get("/api/gaps/software", params={"forge": "capitalforge"})).json()
    assert gaps["total"] >= 1
    assert gaps["items"][0]["forge"] == "capitalforge"
