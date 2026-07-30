"""URN scheme (§12.1). `urn:gc:<domain>:<kind>:<canonical_id>`.

Generalized from the hard-coded `urn:gc:village:...` — the domain is now a segment (default
"village" for back-compat) and `kind` is validated against the canonical taxonomy.
"""

from __future__ import annotations

_PREFIX = "urn:gc"
_DEFAULT_DOMAIN = "village"

# The canonical object kinds (§12.1) + the kinds SimForge's own objects already emit.
KINDS: tuple[str, ...] = (
    "agent",
    "department",
    "forge_cap",
    "forge_context",
    "pack",
    "scenario",
    "policy",
    "rubric",
    "model",
    "tool",
    "jurisdiction",
    "evidence_bundle",
    "cert_snapshot",
    "constitution_version",
    "cert",
    "evidence",
    "constitution",
)


class UrnError(Exception):
    """Malformed URN or unknown kind."""


def build_urn(kind: str, canonical_id: str, domain: str = _DEFAULT_DOMAIN) -> str:
    return f"{_PREFIX}:{domain}:{kind}:{canonical_id}"


def parse_urn(urn: str) -> tuple[str, str, str]:
    """(domain, kind, canonical_id). Raises UrnError on a malformed URN."""
    if not urn.startswith(_PREFIX + ":"):
        raise UrnError(f"URN must start with '{_PREFIX}:': {urn}")
    parts = urn[len(_PREFIX) + 1 :].split(":", 2)
    if len(parts) != 3 or not all(parts):
        raise UrnError(f"URN must be urn:gc:<domain>:<kind>:<id>: {urn}")
    return parts[0], parts[1], parts[2]


def validate_kind(kind: str) -> None:
    if kind not in KINDS:
        raise UrnError(f"Unknown kind '{kind}'. Canonical kinds: {KINDS}")


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


def scenario_urn(scenario_id: str) -> str:
    return build_urn("scenario", scenario_id)


def department_urn(dept_key: str) -> str:
    return build_urn("department", dept_key)
