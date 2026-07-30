"""Object Registry + Lineage (blueprint §C.2 registry, §F.2)."""

from src.services.registry.lineage import add_edge, edges_from, edges_to, find_path, subgraph
from src.services.registry.object_registry import (
    RegistryError,
    find_duplicates,
    merge_entries,
    register_entry,
    resolve_urn,
    tombstone_entry,
)
from src.services.registry.urn import KINDS, UrnError, build_urn, parse_urn

__all__ = [
    "build_urn",
    "parse_urn",
    "KINDS",
    "UrnError",
    "RegistryError",
    "register_entry",
    "resolve_urn",
    "tombstone_entry",
    "find_duplicates",
    "merge_entries",
    "add_edge",
    "edges_from",
    "edges_to",
    "find_path",
    "subgraph",
]
