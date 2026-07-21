"""CCB (Cognitive Context Bundle) composer (blueprint §C.7).

Assembles the 10 Village frameworks into a snapshot with a deterministic content hash.
Pure/read-only: composing a CCB never mutates Village state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from ulid import ULID

from src.services.village.reader import VillageReader

Phase = Literal["pre", "post"]

FRAMEWORKS = ("game", "mate", "soul", "breath", "fot", "hfm", "arc", "echo", "drift", "ame")


@dataclass(frozen=True)
class CCBData:
    snapshot_id: str
    agent_village_id: str
    phase: Phase
    taken_at: datetime
    content_hash: str
    village_schema_fingerprint: str
    frameworks: dict[str, object] = field(default_factory=dict)

    def framework(self, name: str) -> object:
        return self.frameworks.get(name, {})


class CCBComposer:
    def __init__(self, reader: VillageReader) -> None:
        self.reader = reader

    def compose(
        self,
        agent_village_id: str,
        phase: Phase,
        village_schema_fingerprint: str | None = None,
    ) -> CCBData:
        fingerprint = (
            village_schema_fingerprint
            if village_schema_fingerprint is not None
            else self.reader.get_village_schema_fingerprint()
        )

        frameworks: dict[str, object] = {
            "game": self.reader.get_agent_game(agent_village_id),
            "mate": self.reader.get_agent_mate(agent_village_id),
            "soul": self.reader.get_agent_soul(agent_village_id),
            "breath": self.reader.get_agent_breath(agent_village_id),
            "fot": self.reader.get_agent_fot(agent_village_id),
            "hfm": self.reader.get_agent_hfm(agent_village_id),
            "arc": self.reader.get_agent_arc(agent_village_id),
            "echo": self.reader.get_agent_echo(agent_village_id),
            "drift": self.reader.get_agent_drift(agent_village_id),
            "ame": self.reader.get_agent_ame(agent_village_id),
        }

        content_hash = hashlib.sha256(
            json.dumps(frameworks, sort_keys=True, default=str).encode()
        ).hexdigest()

        return CCBData(
            snapshot_id=str(ULID()),
            agent_village_id=agent_village_id,
            phase=phase,
            taken_at=datetime.now(UTC),
            content_hash=content_hash,
            village_schema_fingerprint=fingerprint,
            frameworks=frameworks,
        )
