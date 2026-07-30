"""Supply-Chain & Third-Party Dependency Governance (v1.2).

Generates a Software Bill of Materials from the repo's own manifests (pyproject.toml + the web
package.json) and applies governance policy: every component is checked for a version pin and
against a configurable denylist. A live vulnerability feed is an external seam — absent it, we do
NOT fabricate CVE data; we surface what is verifiable from the manifests (pin discipline, denylist).
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from src.config import settings

# apps/api/src/services/supply_chain/sbom.py → repo root is parents[5].
_REPO_ROOT = Path(__file__).resolve().parents[5]
_PYPROJECT = _REPO_ROOT / "apps" / "api" / "pyproject.toml"
_WEB_PKG = _REPO_ROOT / "apps" / "web" / "package.json"

# A requirement is "pinned" if it fixes an exact version (==x, or an exact npm version like 1.2.3).
_PY_NAME = re.compile(r"^([A-Za-z0-9_.\-]+)")
_EXACT_NPM = re.compile(r"^\d+\.\d+\.\d+")


@dataclass
class Component:
    name: str
    version: str
    ecosystem: str
    scope: str  # runtime | dev | optional
    pinned: bool
    flags: list[str]


def _denylist() -> set[str]:
    raw = getattr(settings, "supply_chain_denylist", "") or ""
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def _py_component(req: str, scope: str, deny: set[str]) -> Component | None:
    req = req.strip()
    m = _PY_NAME.match(req)
    if not m:
        return None
    name = m.group(1)
    constraint = req[len(name) :].strip()
    pinned = "==" in constraint
    flags: list[str] = []
    if not pinned:
        flags.append("unpinned")
    if name.lower() in deny:
        flags.append("denylisted")
    return Component(
        name=name,
        version=constraint or "*",
        ecosystem="pypi",
        scope=scope,
        pinned=pinned,
        flags=flags,
    )


def _npm_component(name: str, spec: str, scope: str, deny: set[str]) -> Component:
    pinned = bool(_EXACT_NPM.match(spec.strip()))
    flags: list[str] = []
    if not pinned:
        flags.append("unpinned")
    if name.lower() in deny:
        flags.append("denylisted")
    return Component(
        name=name, version=spec, ecosystem="npm", scope=scope, pinned=pinned, flags=flags
    )


@lru_cache(maxsize=1)
def _read_manifests() -> tuple[dict, dict]:
    py: dict = {}
    web: dict = {}
    if _PYPROJECT.exists():
        py = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    if _WEB_PKG.exists():
        web = json.loads(_WEB_PKG.read_text(encoding="utf-8"))
    return py, web


def generate_sbom() -> dict:
    """Build the SBOM + governance flags from the repo manifests."""
    deny = _denylist()
    py, web = _read_manifests()
    components: list[Component] = []

    project = py.get("project", {})
    for req in project.get("dependencies", []) or []:
        c = _py_component(req, "runtime", deny)
        if c:
            components.append(c)
    for group, reqs in (project.get("optional-dependencies", {}) or {}).items():
        scope = "dev" if group in ("dev", "test") else "optional"
        for req in reqs or []:
            c = _py_component(req, scope, deny)
            if c:
                components.append(c)

    for name, spec in (web.get("dependencies", {}) or {}).items():
        components.append(_npm_component(name, str(spec), "runtime", deny))
    for name, spec in (web.get("devDependencies", {}) or {}).items():
        components.append(_npm_component(name, str(spec), "dev", deny))

    components.sort(key=lambda c: (c.ecosystem, c.name))
    flagged = [c for c in components if c.flags]
    return {
        "generated": True,
        "vuln_feed_configured": bool(getattr(settings, "supply_chain_vuln_feed_url", "")),
        "counts": {
            "total": len(components),
            "runtime": sum(1 for c in components if c.scope == "runtime"),
            "flagged": len(flagged),
            "denylisted": sum(1 for c in components if "denylisted" in c.flags),
            "unpinned": sum(1 for c in components if "unpinned" in c.flags),
        },
        "components": [
            {
                "name": c.name,
                "version": c.version,
                "ecosystem": c.ecosystem,
                "scope": c.scope,
                "pinned": c.pinned,
                "flags": c.flags,
            }
            for c in components
        ],
    }
