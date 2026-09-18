"""Read-only Village OS filesystem reader (blueprint §C.6).

Reads an agent's 10 cognitive frameworks from the VillageData tree. The reader NEVER
writes to Village (sandbox isolation invariant). Path conventions match
`scripts/make-village-fixture.py`; real Village paths are reconciled later.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from src.config import settings
from src.services.village.agent_db import VillageAgentDb, VillageAgentDbError


class VillageReaderError(Exception):
    """Base error for Village reads."""


class VillageSchemaFingerprintMismatch(VillageReaderError):
    """Raised when the Village structural fingerprint drifts from the expected value."""


# Structural subdirs that contribute to the schema fingerprint.
_FINGERPRINT_SUBDIRS = ("knowledge", "emotional_ledger", "memory", "tasks")


@dataclass(frozen=True)
class VillageReader:
    village_data_path: Path
    #: The live Village database (ADR-0065). When set, IDENTITY is read from it and the tree is
    #: used only for the frameworks the database does not hold.
    #:
    #: `None` means identity falls back to `agents/<id>/identity.json` - a SNAPSHOT, and the
    #: snapshot has been wrong before: the tree and the database shared one agent out of 114 and
    #: 186. That path is kept for test harnesses and for a caller that deliberately points at a
    #: fixture, and `identity_source` says which one is in use so it is never a silent question.
    village_db_path: Path | None = None

    @classmethod
    def from_settings(cls) -> VillageReader:
        path = Path(settings.village_data_path)
        if not path.exists():
            raise VillageReaderError(f"VILLAGE_DATA_PATH does not exist: {path}")
        if not path.is_dir():
            raise VillageReaderError(f"VILLAGE_DATA_PATH is not a directory: {path}")
        # Configured by default, so a real deployment is database-backed unless somebody empties
        # the setting on purpose. A path that is set and missing is NOT quietly ignored - the
        # first identity read raises and names it.
        configured = (settings.village_db_path or "").strip()
        return cls(
            village_data_path=path,
            village_db_path=Path(configured) if configured else None,
        )

    @property
    def identity_source(self) -> str:
        """`village_db` or `snapshot`. Surfaced rather than inferred: which one is in use decides
        whether an identity describes the population that is running."""
        return "village_db" if self.village_db_path is not None else "snapshot"

    @property
    def agent_db(self) -> VillageAgentDb | None:
        return VillageAgentDb(self.village_db_path) if self.village_db_path else None

    # -- helpers ----------------------------------------------------------

    def agent_root(self, agent_village_id: str) -> Path:
        p = self.village_data_path / "agents" / agent_village_id
        if not p.exists():
            raise VillageReaderError(f"Agent not found: {agent_village_id}")
        return p

    @staticmethod
    def _read_json(path: Path) -> dict:
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _read_json_dir(directory: Path) -> dict:
        out: dict = {}
        if not directory.exists():
            return out
        for jf in sorted(directory.glob("*.json")):
            with open(jf, encoding="utf-8") as f:
                out[jf.stem] = json.load(f)
        return out

    # -- identity ---------------------------------------------------------

    def get_agent_identity(self, agent_village_id: str) -> dict:
        """Who this agent is. Raises `VillageReaderError` when nobody of that id exists.

        **From the live database when one is configured** (ADR-0065). A miss there is a miss: the
        database is the population, so an agent it does not have is an agent that does not exist,
        and falling through to the tree would answer from the snapshot that caused this ruling.

        A lookup that finds nothing RAISES rather than returning `{}`. It used to return `{}` for
        an agent with no `identity.json`, which `AgentRuntime._safe` swallowed and the prompt
        papered over with the id as a name - the blank pass ADR-0061 closed. The raise is what
        `check_agent_identity` turns into a named refusal.
        """
        db = self.agent_db
        if db is not None:
            # Re-raised as a Village read failure rather than left as its own type:
            # `AgentRuntime._safe` catches `VillageReaderError` and nothing else, and a database
            # outage must not become an uncaught 500 in a scenario run.
            try:
                identity = db.identity(agent_village_id)
            except VillageAgentDbError as exc:
                raise VillageReaderError(str(exc)) from exc
            if identity is None:
                raise VillageReaderError(
                    f"Agent not found: {agent_village_id} (not in {self.village_db_path})"
                )
            return identity

        # No database configured: the snapshot, and `agent_root` already raises on a miss.
        identity = self._read_json(self.agent_root(agent_village_id) / "identity.json")
        if not identity:
            raise VillageReaderError(
                f"Agent not found: {agent_village_id} (no identity.json under "
                f"{self.village_data_path})"
            )
        return identity

    # -- BREATH -----------------------------------------------------------

    def get_agent_breath(self, agent_village_id: str) -> dict:
        knowledge = self.agent_root(agent_village_id) / "knowledge"
        breath: dict = {}
        for component in ("beliefs", "rituals", "ethics", "attachments", "traditions", "habits"):
            breath[component] = self._read_json_dir(knowledge / component)
        return breath

    # -- FOT / HFM / MATE (indexed) --------------------------------------

    def get_agent_fot(self, agent_village_id: str) -> dict:
        return self._read_json(
            self.agent_root(agent_village_id) / "knowledge" / "fot" / "fot_index.json"
        )

    def get_agent_hfm(self, agent_village_id: str) -> dict:
        return self._read_json(
            self.agent_root(agent_village_id) / "knowledge" / "hfm" / "hfm_index.json"
        )

    def get_agent_mate(self, agent_village_id: str) -> dict:
        return self._read_json(
            self.agent_root(agent_village_id) / "knowledge" / "mate" / "mate_index.json"
        )

    # -- SOUL -------------------------------------------------------------

    def get_agent_soul(self, agent_village_id: str) -> dict:
        ledger = self._read_json_dir(self.agent_root(agent_village_id) / "emotional_ledger")
        return {"ledger": ledger}

    # -- Episodes ---------------------------------------------------------

    def get_agent_episodes(self, agent_village_id: str, limit: int = 10) -> list[dict]:
        episodes_dir = self.agent_root(agent_village_id) / "knowledge" / "learned" / "episodes"
        if not episodes_dir.exists():
            return []
        files = sorted(episodes_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[
            :limit
        ]
        episodes: list[dict] = []
        for ep in files:
            with open(ep, encoding="utf-8") as f:
                episodes.append(json.load(f))
        return episodes

    # -- memory/* framework states ---------------------------------------

    def _memory_state(self, agent_village_id: str, filename: str, default: dict) -> dict:
        data = self._read_json(self.agent_root(agent_village_id) / "memory" / filename)
        return data or default

    def get_agent_arc(self, agent_village_id: str) -> dict:
        return self._memory_state(
            agent_village_id,
            "arc_state.json",
            {"current_phase": "unknown", "dominant_themes": [], "identity_dimensions": {}},
        )

    def get_agent_echo(self, agent_village_id: str) -> dict:
        return self._memory_state(
            agent_village_id, "echo_state.json", {"regret_load": 0.0, "recent_regrets": []}
        )

    def get_agent_drift(self, agent_village_id: str) -> dict:
        return self._memory_state(
            agent_village_id, "drift_state.json", {"drift_score": 0.0, "flagged": False}
        )

    def get_agent_ame(self, agent_village_id: str) -> dict:
        return self._memory_state(
            agent_village_id,
            "ame_state.json",
            {"reputation": 0.5, "trajectory": "stable", "recent_delta": 0.0},
        )

    def get_agent_game(self, agent_village_id: str) -> dict:
        return self._memory_state(
            agent_village_id, "game_state.json", {"active_goals": [], "recent_events": []}
        )

    # -- Schema fingerprint (drift detection) ----------------------------

    def structural_paths(self) -> list[str]:
        paths: list[str] = []
        agents_dir = self.village_data_path / "agents"
        if not agents_dir.exists():
            return paths
        for agent_dir in sorted(agents_dir.iterdir()):
            if not agent_dir.is_dir():
                continue
            paths.append(agent_dir.name)
            for subdir in _FINGERPRINT_SUBDIRS:
                if (agent_dir / subdir).exists():
                    paths.append(f"{agent_dir.name}/{subdir}")
        return sorted(paths)

    def get_village_schema_fingerprint(self) -> str:
        """SHA-256 over the sorted structural paths of VillageData — detects drift."""
        hasher = hashlib.sha256()
        hasher.update("\n".join(self.structural_paths()).encode())
        return hasher.hexdigest()

    def verify_fingerprint(self, expected: str) -> None:
        actual = self.get_village_schema_fingerprint()
        if actual != expected:
            raise VillageSchemaFingerprintMismatch(
                f"Village schema drifted. Expected {expected[:12]}…, got {actual[:12]}…"
            )
