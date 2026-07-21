"""Lineage graph — directed edges between URNs (blueprint §C.3.12, §F.2)."""

from __future__ import annotations

from collections import deque

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.registry import LineageEdge

RELATION_TYPES = (
    "produced_by",
    "derived_from",
    "pinned_to",
    "evidenced_by",
    "revoked_by",
    "amends",
)


async def add_edge(
    session: AsyncSession,
    from_urn: str,
    to_urn: str,
    relation_type: str,
    metadata: dict | None = None,
) -> LineageEdge:
    edge = LineageEdge(
        fromUrn=from_urn, toUrn=to_urn, relationType=relation_type, metadata_=metadata
    )
    session.add(edge)
    return edge


async def edges_from(session: AsyncSession, urn: str) -> list[LineageEdge]:
    return list(
        (await session.execute(select(LineageEdge).where(LineageEdge.fromUrn == urn)))
        .scalars()
        .all()
    )


async def edges_to(session: AsyncSession, urn: str) -> list[LineageEdge]:
    return list(
        (await session.execute(select(LineageEdge).where(LineageEdge.toUrn == urn))).scalars().all()
    )


async def find_path(
    session: AsyncSession, from_urn: str, to_urn: str, max_depth: int = 5
) -> list[str] | None:
    """BFS over forward edges up to max_depth. Returns the URN path or None."""
    if from_urn == to_urn:
        return [from_urn]
    queue: deque[tuple[str, list[str]]] = deque([(from_urn, [from_urn])])
    visited = {from_urn}
    while queue:
        node, path = queue.popleft()
        if len(path) > max_depth:
            continue
        for edge in await edges_from(session, node):
            if edge.toUrn == to_urn:
                return path + [edge.toUrn]
            if edge.toUrn not in visited:
                visited.add(edge.toUrn)
                queue.append((edge.toUrn, path + [edge.toUrn]))
    return None


async def subgraph(session: AsyncSession, urn: str, hops: int = 2) -> dict:
    """Return the neighborhood (both directions) within `hops` of a URN."""
    nodes: set[str] = {urn}
    edges: list[LineageEdge] = []
    frontier = {urn}
    for _ in range(hops):
        next_frontier: set[str] = set()
        for node in frontier:
            for edge in (await edges_from(session, node)) + (await edges_to(session, node)):
                edges.append(edge)
                for u in (edge.fromUrn, edge.toUrn):
                    if u not in nodes:
                        nodes.add(u)
                        next_frontier.add(u)
        frontier = next_frontier
    seen: set[str] = set()
    uniq = []
    for e in edges:
        key = f"{e.fromUrn}|{e.toUrn}|{e.relationType}"
        if key not in seen:
            seen.add(key)
            uniq.append(e)
    return {
        "nodes": sorted(nodes),
        "edges": [{"from": e.fromUrn, "to": e.toUrn, "relation": e.relationType} for e in uniq],
    }
