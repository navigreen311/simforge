"""Forge adapter registry/factory (blueprint Part E)."""

from __future__ import annotations

from src.services.forges.base import ForgeAdapter, NullForgeAdapter
from src.services.forges.capitalforge import LocalCapitalForgeAdapter
from src.services.forges.cre_forge import LocalCREForgeAdapter
from src.services.forges.medlink_pro import LocalMedLinkProAdapter
from src.services.forges.visionaudioforge import LocalVAFAdapter
from src.services.forges.voiceforge import LocalVoiceForgeAdapter

KNOWN_FORGES = (
    "voiceforge",
    "vaf",
    "medlink-pro",
    "cre-forge",
    "funnelforge",
    "capitalforge",
)


def get_forge_adapter(forge: str) -> ForgeAdapter:
    """Resolve a Forge name → adapter. Real: CapitalForge/VAF/VoiceForge/CRE/medlink-pro."""
    if forge == "capitalforge":
        return LocalCapitalForgeAdapter()
    if forge == "vaf":
        return LocalVAFAdapter()
    if forge == "voiceforge":
        return LocalVoiceForgeAdapter()
    if forge == "cre-forge":
        return LocalCREForgeAdapter()
    if forge == "medlink-pro":
        return LocalMedLinkProAdapter()
    return NullForgeAdapter(forge)


def forge_of_cap(cap: str) -> str:
    """The forge name from a capability string like 'capitalforge.emd.release'."""
    return cap.split(".", 1)[0]
