"""Unit tests for URN + lineage graph."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.registry import (
    add_edge,
    find_duplicates,
    find_path,
    register_entry,
    resolve_urn,
    subgraph,
)
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


# --- §12.1 depth: generalized URN, 14-kind taxonomy, dedup, merge ---


def test_urn_parse_and_custom_domain() -> None:
    from src.services.registry.urn import UrnError, parse_urn
    from src.services.registry.urn import build_urn as bu

    assert bu("pack", "p1", domain="greenstone") == "urn:gc:greenstone:pack:p1"
    assert parse_urn("urn:gc:village:agent:x") == ("village", "agent", "x")
    import pytest

    with pytest.raises(UrnError):
        parse_urn("not-a-urn")


def test_kind_taxonomy_validation() -> None:
    from src.services.registry.urn import KINDS, UrnError, validate_kind

    assert "forge_context" in KINDS and "jurisdiction" in KINDS and "rubric" in KINDS
    validate_kind("agent")  # ok
    import pytest

    with pytest.raises(UrnError):
        validate_kind("galaxy")


async def test_find_duplicates(db_session: AsyncSession) -> None:
    # Two URNs for the same (kind, canonical_id) → a dedup candidate.
    await register_entry(db_session, build_urn("agent", "dup", domain="a"), "agent", "dup", {})
    await register_entry(db_session, build_urn("agent", "dup", domain="b"), "agent", "dup", {})
    await register_entry(db_session, agent_urn("unique"), "agent", "unique", {})
    await db_session.commit()
    dups = await find_duplicates(db_session)
    groups = {d["canonical_id"] for d in dups}
    assert "dup" in groups and "unique" not in groups


async def test_merge_redirects_resolution(db_session: AsyncSession) -> None:
    from src.services.registry import merge_entries

    loser = build_urn("agent", "dup", domain="a")
    winner = build_urn("agent", "dup", domain="b")
    await register_entry(db_session, loser, "agent", "dup", {})
    await register_entry(db_session, winner, "agent", "dup", {})
    await db_session.commit()

    await merge_entries(db_session, loser, winner, "admin", "consolidate")
    # Resolving the loser follows the merge pointer to the winner.
    resolved = await resolve_urn(db_session, loser)
    assert resolved is not None and resolved.urn == winner
    # The loser is tombstoned + audited; the winner records the merge.
    raw_loser = await resolve_urn(db_session, loser, follow_merges=False)
    assert raw_loser.tombstoned is True
    assert raw_loser.metadata_["merged_into"] == winner
    win = await resolve_urn(db_session, winner, follow_merges=False)
    assert win.metadata_["merged_from"][0]["from"] == loser


async def test_merge_self_rejected(db_session: AsyncSession) -> None:
    from src.services.registry import RegistryError, merge_entries

    await register_entry(db_session, agent_urn("z"), "agent", "z", {})
    await db_session.commit()
    import pytest

    with pytest.raises(RegistryError):
        await merge_entries(db_session, agent_urn("z"), agent_urn("z"), "admin", "x")


async def test_registry_api_kinds_duplicates_merge(client) -> None:  # noqa: ANN001
    kinds = (await client.get("/api/registry/kinds")).json()["kinds"]
    assert "forge_context" in kinds
    # Register two dupes then merge via the API.
    await client.post(
        "/api/registry/",
        json={"urn": "urn:gc:a:agent:m", "kind": "agent", "canonical_id": "m", "metadata": {}},
    )
    await client.post(
        "/api/registry/",
        json={"urn": "urn:gc:b:agent:m", "kind": "agent", "canonical_id": "m", "metadata": {}},
    )
    dups = (await client.get("/api/registry/duplicates")).json()["duplicates"]
    assert any(d["canonical_id"] == "m" for d in dups)
    merged = await client.post(
        "/api/registry/merge",
        json={"loser_urn": "urn:gc:a:agent:m", "winner_urn": "urn:gc:b:agent:m", "reason": "dedup"},
    )
    assert merged.status_code == 200 and merged.json()["urn"] == "urn:gc:b:agent:m"
    # An unknown kind is rejected by the strict API register.
    bad = await client.post(
        "/api/registry/",
        json={"urn": "urn:gc:x:galaxy:1", "kind": "galaxy", "canonical_id": "1", "metadata": {}},
    )
    assert bad.status_code == 400
