"""Unit tests for URN + lineage graph."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.registry import add_edge, find_path, register_entry, resolve_urn, subgraph
from src.services.registry.urn import agent_urn, build_urn, cert_urn


def test_urn_format() -> None:
    assert build_urn("agent", "jennifer_adams") == "urn:gc:village:agent:jennifer_adams"
    assert cert_urn("abc").startswith("urn:gc:village:cert:")


async def test_register_and_resolve(db_session: AsyncSession) -> None:
    await register_entry(db_session, agent_urn("x"), "agent", "x", {"role": "eng"})
    await db_session.commit()
    e = await resolve_urn(db_session, agent_urn("x"))
    assert e is not None and e.kind == "agent" and e.metadata_["role"] == "eng"


async def test_lineage_path_and_subgraph(db_session: AsyncSession) -> None:
    c, a, p = cert_urn("c1"), agent_urn("a1"), build_urn("pack", "pack.x.v1")
    await add_edge(db_session, c, a, "produced_by")
    await add_edge(db_session, c, p, "derived_from")
    await db_session.commit()

    path = await find_path(db_session, c, p)
    assert path == [c, p]
    assert await find_path(db_session, a, p) is None  # no forward path

    sg = await subgraph(db_session, c, hops=1)
    assert c in sg["nodes"] and a in sg["nodes"] and p in sg["nodes"]
    assert len(sg["edges"]) == 2
