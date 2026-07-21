"""Forge adapter registry/factory (blueprint Part E; ADR-0016 mode selection)."""

from __future__ import annotations

from src.config import settings
from src.services.forges.base import ForgeAdapter, NullForgeAdapter
from src.services.forges.capitalforge import LocalCapitalForgeAdapter
from src.services.forges.cre_forge import LocalCREForgeAdapter
from src.services.forges.funnelforge import LocalFunnelForgeAdapter
from src.services.forges.http_adapter import HttpForgeAdapter
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


def local_forge_adapter(forge: str) -> ForgeAdapter:
    """The in-process Local adapter for a forge (ignores FORGE_MODE); unknown names → Null."""
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
    if forge == "funnelforge":
        return LocalFunnelForgeAdapter()
    return NullForgeAdapter(forge)


def get_forge_adapter(forge: str) -> ForgeAdapter:
    """Resolve a Forge name → adapter, honoring FORGE_MODE (ADR-0016).

    ``http`` + a URL configured for this forge → `HttpForgeAdapter` (real sandbox); otherwise the
    in-process Local adapter. Default is Local, keeping dev/CI deterministic and offline."""
    if settings.forge_mode == "http":
        url = settings.forge_sandbox_urls.get(forge)
        if url:
            return HttpForgeAdapter(forge, url, timeout=settings.forge_request_timeout_seconds)
    return local_forge_adapter(forge)


def forge_of_cap(cap: str) -> str:
    """The forge name from a capability string like 'capitalforge.emd.release'."""
    return cap.split(".", 1)[0]
