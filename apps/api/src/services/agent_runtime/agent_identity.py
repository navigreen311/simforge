"""Can SimForge say who it is examining? If not, it does not examine.

THE RULING (Ivan Green, 17 September 2026)
==========================================

    SimForge refuses to run a battery for an agent it cannot identify. Certifying an agent with
    no name, role or identity is an empty pass.

WHAT MADE THIS REACHABLE
========================

`AgentRuntime.assemble_system_prompt` is deliberately forgiving: every Village read goes through
`_safe`, which swallows `VillageReaderError` and moves on, and the name falls back to the id
itself. That is right for the scenario runner — an agent missing from a dev tree should still be
exercisable — and it is wrong for a certification, because the fallback produces a real prompt
("You are e27fc174-01ac-4090-8127-f4f0cec91bf9, a Village agent") that a model answers, a grader
grades, and a certification records.

**Nothing failed.** The exam ran against a blank and the pass was about nobody. This module is the
check that has to happen BEFORE the forgiving path, and it is deliberately not a change to
`_safe`: the leniency is correct where it lives, and the battery is what must not rely on it.

TWO REASONS, NOT ONE
====================

    not in the village   the id resolves to no agent directory at all
    identity is blank    the directory exists and carries no name or no role

They have different fixes - the first is a missing agent or a wrong id, the second is an agent
whose identity file was never filled in - and a single `unidentified` would send somebody looking
in the wrong place. The repo's rule for declared absence applies to refusals too.

WHAT IS *NOT* CHECKED HERE
==========================

Whether the id is the right SHAPE. The Office sends its own `office_agent_id` (a uuid) and the
Village keys agents by a ref like `victor_serath`; the mapping lives in The Office's
`office_agent_identity.village_agent_ref` and does not currently cross the boundary. That is a
real gap and it is a seam to build, not a string to validate - a uuid that happened to name a
Village directory would be perfectly identifiable, and a ref that names nothing would not.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.services.village.reader import VillageReader, VillageReaderError

#: The agent id resolves to no agent in the Village tree SimForge reads.
AGENT_NOT_IN_VILLAGE = "the_agent_is_not_in_the_village_tree"
#: The agent resolves and its identity says nothing: no name, or no role.
AGENT_IDENTITY_BLANK = "the_agent_identity_carries_no_name_or_role"


@dataclass(frozen=True, slots=True)
class AgentIdentityCheck:
    """`reason` is None exactly when the agent may be examined."""

    reason: str | None
    detail: str
    name: str = ""
    role: str = ""

    @property
    def ok(self) -> bool:
        return self.reason is None


def check_agent_identity(reader: VillageReader, agent_id: str) -> AgentIdentityCheck:
    """Whether SimForge can say who `agent_id` is.

    Reads only `identity.json` — the layer that carries the name and the role. The other nine
    frameworks are context and a thin one is not an identity failure; an agent with no episodes is
    still that agent, and refusing on them would refuse most of a dev tree for the wrong reason.
    """
    try:
        identity = reader.get_agent_identity(agent_id)
    except VillageReaderError as exc:
        return AgentIdentityCheck(
            AGENT_NOT_IN_VILLAGE,
            f"{exc}. SimForge reads `{reader.village_data_path}/agents/<id>/identity.json`, and "
            f"there is no such agent for {agent_id!r}. A battery run now would examine a prompt "
            "that names an id and nothing else, and certify it.",
        )

    name = str(identity.get("name") or "").strip()
    role = str(identity.get("role") or "").strip()
    if not name or not role:
        missing = " and ".join(n for n, v in (("name", name), ("role", role)) if not v)
        return AgentIdentityCheck(
            AGENT_IDENTITY_BLANK,
            f"{agent_id!r} resolves to an agent whose identity carries no {missing}. A "
            "certification records which agent passed; one that cannot name the agent is a pass "
            "about nobody.",
            name=name,
            role=role,
        )

    return AgentIdentityCheck(None, f"{name} ({role})", name=name, role=role)


__all__ = [
    "AGENT_IDENTITY_BLANK",
    "AGENT_NOT_IN_VILLAGE",
    "AgentIdentityCheck",
    "check_agent_identity",
]
