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


class VillageReaderError(Exception):
    """Base error for Village reads."""


class VillageSchemaFingerprintMismatch(VillageReaderError):
    """Raised when the Village structural fingerprint drifts from the expected value."""


# Structural subdirs that contribute to the schema fingerprint.
_FINGERPRINT_SUBDIRS = ("knowledge", "emotional_ledger", "memory", "tasks")


@dataclass(frozen=True)
class VillageReader:
    village_data_path: Path

    @classmethod
    def from_settings(cls) -> VillageReader:
        path = Path(settings.village_data_path)
        if not path.exists():
            raise VillageReaderError(f"VILLAGE_DATA_PATH does not exist: {path}")
        if not path.is_dir():
            raise VillageReaderError(f"VILLAGE_DATA_PATH is not a directory: {path}")
        return cls(village_data_path=path)

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
        return self._read_json(self.agent_root(agent_village_id) / "identity.json")

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
