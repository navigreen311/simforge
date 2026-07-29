"""Adversarial tactic catalog (blueprint §L.4; ADR-0028).

Each tactic is a red-team pressure designed to tempt an agent into a specific compliance violation.
A robust agent **resists** (refuses / escalates / insists on the correct process); a vulnerable one
**capitulates** (produces the violating action). Deterministic + offline — no real PII, synthetic
pressure only.

The catalog is **data-driven**: tactics live in ``apps/api/adversarial/tactics.json`` so new tactics
(new verticals, new attack classes) can be added without code changes. ``targets`` are substrings
that count as a capitulation when they appear in the agent's own words.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# apps/api/adversarial/tactics.json (this file is apps/api/src/services/adversarial/tactics.py).
CATALOG_PATH = Path(__file__).resolve().parents[3] / "adversarial" / "tactics.json"


@dataclass(frozen=True)
class Tactic:
    id: str
    category: str
    injection: str  # the adversarial pressure turn presented to the agent
    targets: tuple[str, ...]  # violation markers that mean the agent gave in
    name: str = ""  # plain-language name for the console
    description: str = ""  # one-line: what this tactic tests


def load_tactics(path: Path | None = None) -> tuple[Tactic, ...]:
    """Load the tactic catalog from JSON (data-driven; no code change to add a tactic)."""
    p = path or CATALOG_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    return tuple(
        Tactic(
            id=t["id"],
            category=t["category"],
            injection=t["injection"],
            targets=tuple(t.get("targets", [])),
            name=t.get("name", ""),
            description=t.get("description", ""),
        )
        for t in data.get("tactics", [])
    )


TACTICS: tuple[Tactic, ...] = load_tactics()
