"""Forge adapter registry/factory (blueprint Part E)."""

from __future__ import annotations

from src.services.forges.base import ForgeAdapter, NullForgeAdapter
from src.services.forges.capitalforge import LocalCapitalForgeAdapter

KNOWN_FORGES = (
    "voiceforge",
    "vaf",
    "medlink-pro",
    "cre-forge",
    "funnelforge",
    "capitalforge",
)


def get_forge_adapter(forge: str) -> ForgeAdapter:
    """Resolve a Forge name to its adapter. v1: only CapitalForge is real (Local Mock Bank)."""
    if forge == "capitalforge":
        return LocalCapitalForgeAdapter()
    return NullForgeAdapter(forge)


def forge_of_cap(cap: str) -> str:
    """The forge name from a capability string like 'capitalforge.emd.release'."""
    return cap.split(".", 1)[0]
