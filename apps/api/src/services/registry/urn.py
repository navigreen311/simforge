"""URN scheme (blueprint §C.2). urn:gc:village:<kind>:<canonical_id>."""

from __future__ import annotations

_NS = "urn:gc:village"


def build_urn(kind: str, canonical_id: str) -> str:
    return f"{_NS}:{kind}:{canonical_id}"


def agent_urn(village_agent_id: str) -> str:
    return build_urn("agent", village_agent_id)


def pack_urn(pack_id: str) -> str:
    return build_urn("pack", pack_id)


def cert_urn(cert_id: str) -> str:
    return build_urn("cert", cert_id)


def constitution_urn(version: str) -> str:
    return build_urn("constitution", version)


def evidence_urn(snapshot_id: str) -> str:
    return build_urn("evidence", snapshot_id.replace(":", "_"))
