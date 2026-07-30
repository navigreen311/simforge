"""Knowledge Graph / Domain Ontology (v1.1): entities, relations, integrity, scenario grounding."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ontology import OntologyRelation
from src.models.pack import Pack, Scenario


async def test_build_graph_and_relation_validation(client: AsyncClient) -> None:
    await client.post(
        "/api/ontology/lending/entities", json={"name": "Borrower", "category": "actor"}
    )
    await client.post("/api/ontology/lending/entities", json={"name": "Loan", "category": "object"})
    ok = await client.post(
        "/api/ontology/lending/relations",
        json={"from_entity": "Borrower", "relation": "applies_for", "to_entity": "Loan"},
    )
    assert ok.status_code == 200

    # A relation to an unknown entity is rejected.
    bad = await client.post(
        "/api/ontology/lending/relations",
        json={"from_entity": "Borrower", "relation": "owns", "to_entity": "Spaceship"},
    )
    assert bad.status_code == 400
    assert "not in the ontology" in bad.json()["detail"]


async def test_duplicate_entity_rejected(client: AsyncClient) -> None:
    await client.post("/api/ontology/x/entities", json={"name": "Thing"})
    dup = await client.post("/api/ontology/x/entities", json={"name": "Thing"})
    assert dup.status_code == 400


async def test_graph_grounding_and_integrity(client: AsyncClient, db_session: AsyncSession) -> None:
    # A pack + scenario whose title references "Underwriter" but not "Ghost".
    db_session.add(
        Pack(
            id="pk-lend",
            packId="pack.lending.v1",
            name="lending",
            version="v1",
            ownerVenture="lending2",
            ownerHuman="ivan",
            phiRequired=False,
            executionModeDefault="sandbox",
            narrativeModeDefault="protected",
            locale="en",
            rubricProfile="default",
            yamlPath="p.yml",
            yamlHash="h",
        )
    )
    db_session.add(
        Scenario(
            scenarioId="scn.lend.1",
            packId="pk-lend",
            title="Underwriter reviews a risky loan",
            tier="foundational",
            testedAgentVillageId="a",
            yamlPath="p.yml",
            yamlHash="h",
            sloSeconds=60,
            isGolden=False,
        )
    )
    await db_session.commit()

    for name in ("Underwriter", "Ghost"):
        await client.post("/api/ontology/lending2/entities", json={"name": name})
    # Inject a dangling relation directly (bypassing validation) to exercise the integrity check.
    db_session.add(
        OntologyRelation(
            venture="lending2", fromEntity="Underwriter", relation="haunts", toEntity="Nowhere"
        )
    )
    await db_session.commit()

    g = (await client.get("/api/ontology/lending2")).json()
    assert "Underwriter" in g["grounding"]["grounded"]
    assert "Ghost" in g["grounding"]["orphans"]
    assert g["grounding"]["grounded_pct"] == 0.5
    assert g["integrity"]["ok"] is False
    assert g["integrity"]["dangling_relations"][0]["to"] == "Nowhere"


async def test_empty_graph(client: AsyncClient) -> None:
    g = (await client.get("/api/ontology/nothing")).json()
    assert g["entities"] == []
    assert g["grounding"]["grounded_pct"] == 0.0
    assert g["integrity"]["ok"] is True
