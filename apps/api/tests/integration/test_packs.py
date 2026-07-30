"""Integration tests for Pack ingestion + packs/scenarios endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bank_scenario import BankScenario
from src.utils.time import utcnow

# apps/api/tests/integration/test_packs.py → repo root is parents[4]
REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")
MEDLINK = str(REPO_ROOT / "packs" / "medlink-pro" / "v1")


async def test_ingest_and_list_pack(client: AsyncClient) -> None:
    # Ingest via absolute path
    resp = await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["pack_id"] == "pack.greenstone.v1"
    # Corpus is full-scale (Wave 5); assert the floor + that the golden seed survives.
    assert body["scenarios"] >= 3

    # List
    lst = await client.get("/api/packs/")
    assert lst.status_code == 200
    assert lst.json()["total"] == 1

    # Detail
    detail = await client.get("/api/packs/pack.greenstone.v1")
    assert detail.status_code == 200
    d = detail.json()
    assert d["ownerVenture"] == "greenstone"
    assert len(d["scenarios"]) >= 3
    assert any(s["scenarioId"] == "scn.gs.src.001" for s in d["scenarios"])
    assert "tcpa" in d["complianceFlags"]


async def test_ingest_is_idempotent(client: AsyncClient) -> None:
    for _ in range(2):
        resp = await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
        assert resp.status_code == 200
    lst = await client.get("/api/packs/")
    assert lst.json()["total"] == 1  # no duplicate pack


async def test_scenarios_endpoints(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": MEDLINK})

    all_scen = await client.get("/api/scenarios/", params={"pack_id": "pack.medlink-pro.v1"})
    assert all_scen.status_code == 200
    assert all_scen.json()["total"] >= 3

    crisis = await client.get("/api/scenarios/", params={"tier": "advanced_crisis"})
    assert crisis.status_code == 200
    assert crisis.json()["total"] >= 1

    detail = await client.get("/api/scenarios/scn.ml.cred.001")
    assert detail.status_code == 200
    assert detail.json()["testedAgentVillageId"] == "nina_okafor"


async def test_sign_pack(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    resp = await client.post("/api/packs/pack.greenstone.v1/sign", json={"signed_by": "ivan"})
    assert resp.status_code == 200
    assert resp.json()["signedBy"] == "ivan"


async def test_list_is_enriched_with_scenario_summary(client: AsyncClient) -> None:
    # Part A: the list row carries scenario count, tier spread, golden count, and flags.
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    item = (await client.get("/api/packs/")).json()["items"][0]
    assert item["scenarioCount"] >= 3
    assert sum(item["tierCounts"].values()) == item["scenarioCount"]
    assert set(item["tierCounts"]) == {"foundational", "intermediate", "advanced_crisis"}
    assert item["goldenCount"] >= 0
    assert "tcpa" in item["complianceFlags"]


async def test_flag_catalog_labels_every_used_flag(client: AsyncClient) -> None:
    # Every flag actually used by a pack must be labeled (no unexplained chip).
    await client.post("/api/packs/", json={"pack_dir": MEDLINK})
    cat = (await client.get("/api/packs/flag-catalog")).json()
    for flag in ["hipaa", "hcqc_nv", "oig_sam", "i9"]:
        assert flag in cat["flags"], flag
        assert cat["flags"][flag]["label"]
        assert cat["flags"][flag]["tooltip"]
    # HIPAA is a PHI flag and maps to the federal jurisdiction.
    assert cat["flags"]["hipaa"]["phi"] is True
    assert cat["flags"]["hipaa"]["jurisdiction"] == "US-FED"
    # The one catalog also covers every Jurisdiction-engine flag, even for states with no pack yet
    # (so the Jurisdiction Engine page's Required / PHI-gated columns are legible). Single source.
    for flag in ["adhs_az", "ahca_fl", "hhsc_tx", "nysdoh_ny"]:
        assert flag in cat["flags"], flag
        assert cat["flags"][flag]["label"] and cat["flags"][flag]["tooltip"]
    # Legend copy is present for the non-flag chips.
    assert "venture" in cat["legend"] and "phi" in cat["legend"] and "sandbox" in cat["legend"]


async def test_unknown_flag_gets_readable_fallback() -> None:
    # A flag with no catalog entry still gets a humanized label, never blank.
    from src.services.packs.flag_catalog import describe_flag

    d = describe_flag("some_new_flag")
    assert d["label"] == "Some New Flag"
    assert d["tooltip"]
    assert d["phi"] is False


# ── Part B: create / edit a Pack from committed scenarios ───────────────────


@pytest.fixture
def _packs_root(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Write generated packs to a temp dir, not the repo's packs/."""
    from src.config import settings

    root = tmp_path / "packs"
    root.mkdir()
    monkeypatch.setattr(settings, "packs_root", str(root))
    return root


async def _seed_bank(
    session: AsyncSession, scenario_id: str, status: str = "committed", tier: str = "foundational"
) -> None:
    now = utcnow()
    session.add(
        BankScenario(
            publicId=f"pub_{scenario_id}",
            scenarioId=scenario_id,
            title=f"Test scenario {scenario_id}",
            pack="greenstone",
            family="src",
            tier=tier,
            situation="A synthetic situation the agent must handle correctly and honestly.",
            expectedBehaviors=["confirm consent", "stay compliant"],
            status=status,
            aiDrafted=False,
            sourceType="manual",
            createdBy="ivan",
            createdAt=now,
            updatedAt=now,
        )
    )
    await session.commit()


def _create_body(scenario_id: str) -> dict:
    return {
        "title": "Argus Security Triage",
        "ownerVenture": "argus",
        "rubricProfile": "argus.default",
        "phiRequired": False,
        "complianceFlags": [],
        "scenarios": [
            {"scenarioId": scenario_id, "testedAgentVillageId": "nina_okafor", "sloSeconds": 300}
        ],
    }


async def test_create_pack_from_committed_scenario(
    client: AsyncClient, db_session: AsyncSession, _packs_root: Path
) -> None:
    await _seed_bank(db_session, "scn.argus.triage.001")
    resp = await client.post("/api/packs/create", json=_create_body("scn.argus.triage.001"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["packId"] == "pack.argus.v1"
    assert body["scenarios"] == 1

    # It now flows into the normal pack list + detail like any other pack.
    detail = (await client.get("/api/packs/pack.argus.v1")).json()
    assert detail["scenarios"][0]["scenarioId"] == "scn.argus.triage.001"
    assert detail["scenarios"][0]["testedAgentVillageId"] == "nina_okafor"


async def test_only_committed_scenarios_can_enter_a_pack(
    client: AsyncClient, db_session: AsyncSession, _packs_root: Path
) -> None:
    # A scenario that is NOT committed (archived here) is rejected by the guardrail.
    await _seed_bank(db_session, "scn.argus.triage.002", status="archived")
    resp = await client.post("/api/packs/create", json=_create_body("scn.argus.triage.002"))
    assert resp.status_code == 400
    assert "committed" in resp.json()["detail"].lower()


async def test_create_rejects_duplicate_pack(
    client: AsyncClient, db_session: AsyncSession, _packs_root: Path
) -> None:
    await _seed_bank(db_session, "scn.argus.triage.003")
    b = _create_body("scn.argus.triage.003")
    assert (await client.post("/api/packs/create", json=b)).json()["ok"] is True
    # Same venture+version again → refuse (don't overwrite an existing pack).
    dup = await client.post("/api/packs/create", json=_create_body("scn.argus.triage.003"))
    assert dup.status_code == 400
    assert "already exists" in dup.json()["detail"].lower()


async def test_edit_creates_new_version_and_supersedes(
    client: AsyncClient, db_session: AsyncSession, _packs_root: Path
) -> None:
    await _seed_bank(db_session, "scn.argus.triage.010")
    await _seed_bank(db_session, "scn.argus.triage.011", tier="intermediate")
    await client.post("/api/packs/create", json=_create_body("scn.argus.triage.010"))

    # Edit into v2 with a different scenario set.
    v2_body = _create_body("scn.argus.triage.011")
    resp = await client.post("/api/packs/pack.argus.v1/new-version", json=v2_body)
    assert resp.status_code == 200, resp.text
    assert resp.json()["packId"] == "pack.argus.v2"

    # The old version is preserved; the new one records what it supersedes.
    v1 = (await client.get("/api/packs/pack.argus.v1")).json()
    v2 = (await client.get("/api/packs/pack.argus.v2")).json()
    assert v1["scenarios"][0]["scenarioId"] == "scn.argus.triage.010"  # untouched
    assert v2["scenarios"][0]["scenarioId"] == "scn.argus.triage.011"
    assert v2["supersedesPackId"] == "pack.argus.v1"


async def test_authoring_options_exposes_flags_and_suggestions(client: AsyncClient) -> None:
    opts = (await client.get("/api/packs/authoring-options")).json()
    assert "hipaa" in opts["jurisdiction_flags"]
    assert "medlink-pro" in opts["venture_suggestions"]
    assert opts["venture_suggestions"]["medlink-pro"]["phiRequired"] is True
