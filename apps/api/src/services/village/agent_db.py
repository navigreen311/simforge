"""Agent identity, read from the Village's live database.

WHY THIS EXISTS (ADR-0065)
==========================

    Identity is read from the live Village database, not a snapshot. A snapshot that goes stale
    silently is the defect.  — Ivan Green, 17 September 2026

The defect, measured: `village.db` held 186 agents and `VillageData/agents/` held 114 directories,
and **they shared one** (`gardner`). The tree was generated 2026-08-28 at 11:19 for an earlier
cast; the agents that exist now were created at 21:17 that evening and nothing regenerated it. So
`VillageReader` spent three weeks describing a population that was not running, and nothing said
so, because every missing-agent read was swallowed by `AgentRuntime._safe`.

The alternative — regenerate the tree on a cadence — was rejected in the report for one reason: a
regenerated tree is still a snapshot, and the only open question would be how long until the next
one goes stale.

READ-ONLY, AND AGAINST A LIVE WRITER
====================================

The Village is running and writing to this file; `village.db-wal` exists beside it. So the
connection opens `file:<path>?mode=ro` — read-only, and WAL-aware.

**Never `immutable=1`.** That flag promises the file cannot change and lets SQLite skip the WAL
entirely, which against an active writer means reading a stale page and calling it current. The
whole point of this module is not doing that.

THE COLUMNS, AND THE ONE MAPPING THAT IS A DECISION
===================================================

`agents` has around ninety columns. Six are read, by name, so a schema change elsewhere is not a
change here.

**`role` in this database is an org role KEY — `individual_contributor` — and `title` is the job:
`Trend Analyst 2`.** The tree's `role` was a job title, so a straight column swap would have
produced *"You are Victor Serath, a individual_contributor"*, which is not who he is. Ivan's
ruling: the prompt uses the agent's title, falling back to role.

WHAT IS NOT HERE
================

BREATH, FOT, SOUL and episodes. Those still come from the tree, and the tree is still stale for
them — this module closes identity because identity is what `check_agent_identity` refuses on and
what names the agent in the prompt. The rest is sized in the report and is not this change.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

#: The columns read, and nothing else. Named rather than `SELECT *` so a Village schema change is
#: a missing column here - loud - instead of a dict that silently grew.
_COLUMNS = ("id", "name", "role", "title", "department", "backstory", "personality_traits")


class VillageAgentDbError(Exception):
    """The Village agent database could not be read. Never confused with "agent not found"."""


@dataclass(frozen=True, slots=True)
class VillageAgentDb:
    """A read-only window onto the Village's `agents` table."""

    path: Path

    def _connect(self) -> sqlite3.Connection:
        if not self.path.exists():
            raise VillageAgentDbError(
                f"VILLAGE_DB_PATH does not exist: {self.path}. Identity is read from the live "
                "Village database (ADR-0065); without it SimForge cannot say who it would be "
                "examining, and the tree beside it is a snapshot that has been wrong before."
            )
        # `mode=ro`, never `immutable=1` - see the module docstring. A live writer is the normal
        # case here, not an edge one.
        return sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True)

    def identity(self, agent_village_id: str) -> dict | None:
        """One agent's identity, or `None` when the database has no such agent.

        `None` and not an exception: "this agent does not exist" is an ordinary answer to an
        ordinary question, and the caller is the one that knows whether it is fatal.
        `VillageReader.get_agent_identity` turns it into the refusal ADR-0061 already defined.
        """
        columns = ", ".join(f'"{name}"' for name in _COLUMNS)
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    f"SELECT {columns} FROM agents WHERE id = ?", (agent_village_id,)
                ).fetchone()
        except sqlite3.Error as exc:
            raise VillageAgentDbError(f"could not read {self.path}: {exc}") from exc

        return _to_identity(dict(row)) if row is not None else None

    def count(self) -> int:
        """How many agents the live population has.

        For health and for the report, never for grading.
        """
        try:
            with self._connect() as conn:
                return int(conn.execute("SELECT count(*) FROM agents").fetchone()[0])
        except sqlite3.Error as exc:
            raise VillageAgentDbError(f"could not read {self.path}: {exc}") from exc


def _to_identity(row: dict) -> dict:
    """The `identity.json` shape, from the columns that carry it.

    **`title` first, `role` second** (ADR-0065). `role` here is `individual_contributor`; `title`
    is `Trend Analyst 2`. The prompt says "You are <name>, a <role>", and only one of those two is
    an answer to that sentence.

    `personality_traits` is stored as a JSON string. A value that will not parse yields an empty
    list rather than raising: a malformed decoration must not make an agent unidentifiable, and
    `check_agent_identity` refuses on name and role, which are not it.
    """
    traits = row.get("personality_traits")
    if isinstance(traits, str):
        try:
            traits = json.loads(traits)
        except (TypeError, ValueError):
            traits = []
    if not isinstance(traits, list):
        traits = []

    return {
        "village_agent_id": row.get("id") or "",
        "name": (row.get("name") or "").strip(),
        # The decision, in one line.
        "role": (row.get("title") or row.get("role") or "").strip(),
        # Kept beside it rather than discarded: the org role is a real fact and a later reader
        # should not have to guess which of the two `role` meant.
        "org_role": (row.get("role") or "").strip(),
        "department": (row.get("department") or "").strip(),
        "backstory": (row.get("backstory") or "").strip(),
        "personality_traits": traits,
    }


__all__ = ["VillageAgentDb", "VillageAgentDbError"]
