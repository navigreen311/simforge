"""Identity from the live Village database (ADR-0065).

The defect this closes, measured: `village.db` held 186 agents and `VillageData/agents/` held 114
directories, and they shared ONE. The tree had been describing a population that was not running
for three weeks, and nothing said so.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from src.services.agent_runtime.agent_identity import (
    AGENT_IDENTITY_BLANK,
    AGENT_NOT_IN_VILLAGE,
    check_agent_identity,
)
from src.services.village.agent_db import VillageAgentDb, VillageAgentDbError
from src.services.village.reader import VillageReader, VillageReaderError

#: `victor_serath` exactly as the live `village.db` carries him - an org role KEY in `role`, the
#: job in `title`, an EMPTY backstory and NO traits. Every value here was read off the real file.
VICTOR = {
    "id": "victor_serath",
    "name": "Victor Serath",
    "role": "individual_contributor",
    "title": "Trend Analyst 2",
    "department": "Research",
    "backstory": "",
    "personality_traits": "[]",
}

TAYLOR = {
    "id": "taylor_zhang",
    "name": "Taylor Zhang",
    "role": "individual_contributor",
    "title": "Senior Engineer",
    "department": "Engineering",
    "backstory": "Joined Greenstone Engineering after years in fintech infra.",
    "personality_traits": json.dumps(["meticulous", "calm-under-pressure"]),
}


def _db(tmp_path: Path, *rows: dict) -> Path:
    """A Village-shaped `agents` table. Only the columns SimForge reads."""
    path = tmp_path / "village.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE agents (id TEXT PRIMARY KEY, name TEXT, role TEXT, title TEXT, "
        "department TEXT, backstory TEXT, personality_traits TEXT)"
    )
    conn.executemany(
        "INSERT INTO agents VALUES (:id, :name, :role, :title, :department, :backstory, "
        ":personality_traits)",
        rows,
    )
    conn.commit()
    conn.close()
    return path


def _tree(tmp_path: Path, agent_id: str, identity: dict) -> Path:
    root = tmp_path / "VillageData"
    agent_dir = root / "agents" / agent_id
    agent_dir.mkdir(parents=True)
    (agent_dir / "identity.json").write_text(json.dumps(identity), encoding="utf-8")
    return root


# --- the mapping ruling -------------------------------------------------------------------------


def test_the_prompt_uses_the_title_and_not_the_org_role(tmp_path: Path) -> None:
    """**"A individual_contributor" is not who Victor Serath is.**

    The tree's `role` was a job title; this database's `role` is an org role key and its `title` is
    the job. A straight column swap would have produced that sentence in every prompt.
    """
    reader = VillageReader(tmp_path / "VillageData", _db(tmp_path, VICTOR))

    identity = reader.get_agent_identity("victor_serath")

    assert identity["role"] == "Trend Analyst 2"
    assert identity["name"] == "Victor Serath"
    # The org role is kept beside it rather than discarded - it is a real fact, and a later reader
    # should not have to guess which of the two `role` meant.
    assert identity["org_role"] == "individual_contributor"
    assert identity["department"] == "Research"


def test_role_is_the_fallback_when_there_is_no_title(tmp_path: Path) -> None:
    """*Falling back to role*, per the ruling. Better an org key than an unnamed agent, and
    `check_agent_identity` needs a non-empty role to let the exam run at all."""
    reader = VillageReader(tmp_path / "VillageData", _db(tmp_path, {**VICTOR, "title": ""}))

    assert reader.get_agent_identity("victor_serath")["role"] == "individual_contributor"


def test_traits_are_parsed_and_a_malformed_value_is_not_fatal(tmp_path: Path) -> None:
    """A decoration that will not parse must not make an agent unidentifiable: the refusal is
    about name and role, and traits are neither."""
    reader = VillageReader(tmp_path / "VillageData", _db(tmp_path, TAYLOR))
    assert reader.get_agent_identity("taylor_zhang")["personality_traits"] == [
        "meticulous",
        "calm-under-pressure",
    ]

    second = tmp_path / "v2dir"
    second.mkdir()
    broken = VillageReader(
        tmp_path / "v2", _db(second, {**VICTOR, "personality_traits": "{oops"})
    )
    assert broken.get_agent_identity("victor_serath")["personality_traits"] == []


# --- refusing loudly ----------------------------------------------------------------------------


def test_an_agent_the_database_does_not_have_raises(tmp_path: Path) -> None:
    """The database IS the population, so an agent it does not have is an agent that does not
    exist. It raises rather than returning `{}` - which is what `_safe` used to swallow."""
    reader = VillageReader(tmp_path / "VillageData", _db(tmp_path, VICTOR))

    with pytest.raises(VillageReaderError, match="Agent not found: ronan_valek"):
        reader.get_agent_identity("ronan_valek")


def test_the_battery_refuses_that_agent_by_name(tmp_path: Path) -> None:
    """End to end into ADR-0061's guard: the raise becomes the named refusal the battery skips on,
    rather than a blank prompt the exam certifies."""
    reader = VillageReader(tmp_path / "VillageData", _db(tmp_path, VICTOR))

    verdict = check_agent_identity(reader, "ronan_valek")

    assert verdict.reason == AGENT_NOT_IN_VILLAGE
    assert not verdict.ok
    assert "ronan_valek" in verdict.detail


def test_an_agent_with_no_name_is_still_the_other_refusal(tmp_path: Path) -> None:
    """Two reasons, kept apart: a missing agent and a nameless one have different fixes."""
    reader = VillageReader(tmp_path / "VillageData", _db(tmp_path, {**VICTOR, "name": ""}))

    assert check_agent_identity(reader, "victor_serath").reason == AGENT_IDENTITY_BLANK


def test_a_configured_database_that_is_missing_is_loud_not_a_fallback(tmp_path: Path) -> None:
    """**The failure mode this whole ruling is about.**

    A deployment that lost its database must not quietly start answering from the snapshot beside
    it. That is how the tree came to be three weeks stale with nobody noticing.
    """
    tree = _tree(tmp_path, "victor_serath", {"name": "Victor Serath", "role": "Trend Analyst 2"})
    reader = VillageReader(tree, tmp_path / "gone.db")

    with pytest.raises(VillageReaderError, match="VILLAGE_DB_PATH does not exist"):
        reader.get_agent_identity("victor_serath")


def test_the_database_wins_over_a_tree_that_still_has_the_agent(tmp_path: Path) -> None:
    """No fall-through, even when the snapshot has an answer. **Especially** then: a stale tree
    that still holds an agent is the case that produced a wrong answer rather than no answer."""
    tree = _tree(
        tmp_path, "victor_serath", {"name": "Victor Serath", "role": "Junior Analyst 1"}
    )
    reader = VillageReader(tree, _db(tmp_path, VICTOR))

    assert reader.get_agent_identity("victor_serath")["role"] == "Trend Analyst 2"


# --- which source is in use ---------------------------------------------------------------------


def test_the_reader_says_which_source_it_is_using(tmp_path: Path) -> None:
    """Surfaced rather than inferred: which one is in use decides whether an identity describes the
    population that is running."""
    assert VillageReader(tmp_path, _db(tmp_path, VICTOR)).identity_source == "village_db"
    assert VillageReader(tmp_path).identity_source == "snapshot"


def test_the_snapshot_path_also_raises_on_a_miss(tmp_path: Path) -> None:
    """A harness pointed at a tree still refuses an agent it does not have. The snapshot is a
    weaker source, not a more forgiving one."""
    reader = VillageReader(_tree(tmp_path, "taylor_zhang", {"name": "Taylor", "role": "Eng"}))

    with pytest.raises(VillageReaderError):
        reader.get_agent_identity("victor_serath")


def test_a_database_that_cannot_be_read_is_a_village_read_failure(tmp_path: Path) -> None:
    """Re-raised as `VillageReaderError` because `AgentRuntime._safe` catches that and nothing
    else: a database outage must not become an uncaught 500 in a scenario run."""
    corrupt = tmp_path / "village.db"
    corrupt.write_text("this is not a database", encoding="utf-8")

    with pytest.raises(VillageAgentDbError):
        VillageAgentDb(corrupt).identity("victor_serath")

    with pytest.raises(VillageReaderError):
        VillageReader(tmp_path / "VillageData", corrupt).get_agent_identity("victor_serath")
