"""Knowledge Graph / Domain Ontology per venture (v1.1).

Builds a venture's domain model — entities (nodes) and typed relations (edges) — and checks it two
ways: integrity (no relation dangles to an entity that doesn't exist) and scenario grounding (which
ontology entities are actually exercised by the venture's scenarios vs. which are orphans that no
scenario touches). Grounding is a substring match of the entity name in scenario titles — a real,
conservative signal, not a claim of semantic understanding.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ontology import OntologyEntity, OntologyRelation
from src.models.pack import Pack, Scenario


class OntologyError(Exception):
    """Invalid ontology operation."""


async def add_entity(
    session: AsyncSession,
    *,
    venture: str,
    name: str,
    category: str = "concept",
    description: str = "",
) -> OntologyEntity:
    existing = (
        await session.execute(
            select(OntologyEntity).where(
                OntologyEntity.venture == venture, OntologyEntity.name == name
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise OntologyError(f"Entity '{name}' already exists for venture '{venture}'")
    entity = OntologyEntity(venture=venture, name=name, category=category, description=description)
    session.add(entity)
    await session.commit()
    await session.refresh(entity)
    return entity


async def add_relation(
    session: AsyncSession,
    *,
    venture: str,
    from_entity: str,
    relation: str,
    to_entity: str,
) -> OntologyRelation:
    names = {
        e.name
        for e in (
            await session.execute(select(OntologyEntity).where(OntologyEntity.venture == venture))
        )
        .scalars()
        .all()
    }
    missing = [n for n in (from_entity, to_entity) if n not in names]
    if missing:
        raise OntologyError(
            f"Relation endpoints not in the ontology for '{venture}': {', '.join(missing)}"
        )
    edge = OntologyRelation(
        venture=venture, fromEntity=from_entity, relation=relation, toEntity=to_entity
    )
    session.add(edge)
    await session.commit()
    await session.refresh(edge)
    return edge


async def graph(session: AsyncSession, venture: str) -> dict:
    entities = (
        (await session.execute(select(OntologyEntity).where(OntologyEntity.venture == venture)))
        .scalars()
        .all()
    )
    relations = (
        (await session.execute(select(OntologyRelation).where(OntologyRelation.venture == venture)))
        .scalars()
        .all()
    )
    names = {e.name for e in entities}
    # Integrity: a relation whose endpoint isn't a known entity.
    dangling = [
        {"from": r.fromEntity, "relation": r.relation, "to": r.toEntity}
        for r in relations
        if r.fromEntity not in names or r.toEntity not in names
    ]

    # Grounding: which entities appear in the venture's scenario titles.
    titles = (
        (
            await session.execute(
                select(Scenario.title)
                .join(Pack, Scenario.packId == Pack.id)
                .where(Pack.ownerVenture == venture)
            )
        )
        .scalars()
        .all()
    )
    blob = " \n ".join(titles).lower()
    grounded = sorted(e.name for e in entities if e.name.lower() in blob)
    orphans = sorted(e.name for e in entities if e.name.lower() not in blob)

    return {
        "venture": venture,
        "entities": [
            {"name": e.name, "category": e.category, "description": e.description}
            for e in sorted(entities, key=lambda e: e.name)
        ],
        "relations": [
            {"from": r.fromEntity, "relation": r.relation, "to": r.toEntity} for r in relations
        ],
        "integrity": {"dangling_relations": dangling, "ok": len(dangling) == 0},
        "grounding": {
            "grounded": grounded,
            "orphans": orphans,
            "grounded_pct": round(len(grounded) / len(entities), 3) if entities else 0.0,
        },
    }
