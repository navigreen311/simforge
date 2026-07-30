"""Knowledge Graph / Domain Ontology router (v1.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.services.ontology.graph import OntologyError, add_entity, add_relation, graph

router = APIRouter()


class EntityBody(BaseModel):
    name: str
    category: str = "concept"
    description: str = ""


class RelationBody(BaseModel):
    from_entity: str
    relation: str
    to_entity: str


@router.get("/{venture}", dependencies=[Depends(require_role("viewer"))])
async def get_graph(venture: str, session: AsyncSession = Depends(get_session)) -> dict:
    return await graph(session, venture)


@router.post("/{venture}/entities", dependencies=[Depends(require_role("prompt_engineer"))])
async def create_entity(
    venture: str, body: EntityBody, session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        e = await add_entity(
            session,
            venture=venture,
            name=body.name,
            category=body.category,
            description=body.description,
        )
    except OntologyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"name": e.name, "category": e.category, "venture": e.venture}


@router.post("/{venture}/relations", dependencies=[Depends(require_role("prompt_engineer"))])
async def create_relation(
    venture: str, body: RelationBody, session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        r = await add_relation(
            session,
            venture=venture,
            from_entity=body.from_entity,
            relation=body.relation,
            to_entity=body.to_entity,
        )
    except OntologyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"from": r.fromEntity, "relation": r.relation, "to": r.toEntity}
