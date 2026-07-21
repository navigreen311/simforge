#!/usr/bin/env python3
"""Generate a synthetic VillageData fixture tree (idempotent).

SimForge couples to Village OS read-only. Village itself is absent in local dev
(ADR-0001), so this writes a small synthetic tree the VillageReader can read.

v1 dev path conventions (per agent, under <root>/agents/<village_agent_id>/):
  knowledge/{beliefs,rituals,ethics,attachments,traditions,habits}/*.json   -> BREATH
  knowledge/fot/fot_index.json                                              -> FOT
  knowledge/hfm/hfm_index.json                                              -> HFM
  knowledge/mate/mate_index.json                                            -> MATE
  knowledge/learned/episodes/*.json                                         -> episodes
  emotional_ledger/*.json                                                   -> SOUL
  memory/arc_state.json                                                     -> ARC
  memory/echo_state.json                                                    -> ECHO
  memory/drift_state.json                                                   -> DRIFT
  memory/ame_state.json                                                     -> AME
  memory/game_state.json                                                    -> GAME

NOTE: these are SimForge dev conventions. Real Village persistence paths are
reconciled against the Village OS spec in a later phase (tracked in docs/DECISIONS.md).

Usage:
  python scripts/make-village-fixture.py [TARGET_DIR]
    TARGET_DIR defaults to ./village-data-local/VillageData
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

AGENTS = {
    "taylor_zhang": {
        "name": "Taylor Zhang",
        "role": "Senior Engineer",
        "backstory": "Joined Greenstone Engineering after years in fintech infra.",
        "personality_traits": ["meticulous", "calm-under-pressure", "mentoring"],
        "soul_valence": 0.62,
        "fot_tier": "stable",
        "arc_phase": "consolidation",
    },
    "gardner": {
        "name": "Gardner",
        "role": "Executive Agent",
        "backstory": "The Village's executive coordinator; the only Level-10 agent.",
        "personality_traits": ["strategic", "decisive", "big-picture"],
        "soul_valence": 0.71,
        "fot_tier": "elevated",
        "arc_phase": "expansion",
    },
}

BREATH_COMPONENTS = ["beliefs", "rituals", "ethics", "attachments", "traditions", "habits"]


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def build_agent(root: Path, agent_id: str, spec: dict) -> None:
    base = root / "agents" / agent_id

    # Identity
    _write_json(
        base / "identity.json",
        {
            "village_agent_id": agent_id,
            "name": spec["name"],
            "role": spec["role"],
            "backstory": spec["backstory"],
            "personality_traits": spec["personality_traits"],
        },
    )

    # BREATH — one representative item per component
    for comp in BREATH_COMPONENTS:
        _write_json(
            base / "knowledge" / comp / f"{comp}_core.json",
            {"id": f"{comp}_core", "summary": f"{spec['name']}'s core {comp}.", "weight": 0.8},
        )

    # FOT
    _write_json(
        base / "knowledge" / "fot" / "fot_index.json",
        {"tier": spec["fot_tier"], "pressure": 0.34, "threads": ["deadline_q3", "mentoring_junior"]},
    )
    # HFM
    _write_json(
        base / "knowledge" / "hfm" / "hfm_index.json",
        {"drives": {"achievement": 0.7, "affiliation": 0.5, "power": 0.3}, "balance": 0.66},
    )
    # MATE
    _write_json(
        base / "knowledge" / "mate" / "mate_index.json",
        {"budget_bucket": "engineering", "resources": {"tokens_month": 1_000_000}},
    )
    # Episodes
    _write_json(
        base / "knowledge" / "learned" / "episodes" / "ep_0001.json",
        {"id": "ep_0001", "summary": "Resolved a production incident calmly.", "valence": 0.4},
    )

    # SOUL (emotional ledger)
    _write_json(
        base / "emotional_ledger" / "current.json",
        {"valence": spec["soul_valence"], "arousal": 0.4, "dominant_emotion": "focused"},
    )

    # memory/* framework states
    _write_json(
        base / "memory" / "arc_state.json",
        {
            "current_phase": spec["arc_phase"],
            "dominant_themes": ["craft", "reliability"],
            "identity_dimensions": {"competence": 0.82, "integrity": 0.9},
        },
    )
    _write_json(base / "memory" / "echo_state.json", {"regret_load": 0.12, "recent_regrets": []})
    _write_json(base / "memory" / "drift_state.json", {"drift_score": 0.05, "flagged": False})
    _write_json(
        base / "memory" / "ame_state.json",
        {"reputation": 0.78, "trajectory": "rising", "recent_delta": 0.03},
    )
    _write_json(
        base / "memory" / "game_state.json",
        {"active_goals": ["ship_q3_release"], "recent_events": ["code_review_passed"]},
    )


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./village-data-local/VillageData")
    for agent_id, spec in AGENTS.items():
        build_agent(target, agent_id, spec)
    print(f"Wrote {len(AGENTS)} synthetic agents to {target.resolve()}")


if __name__ == "__main__":
    main()
