"""Temporal Realism Engine (v1.1).

Real work isn't turn-synchronous: consequences land after a delay, a signal arrives out of band, a
deadline detonates if it's missed. This engine models those dynamics over *virtual turns* — a
deterministic simulation, not a live clock — so a scenario can be scored on whether the agent
handled time pressure. Scheduled events (delayed/async) fire on their turn; a time-bomb detonates
unless the agent takes its defuse action on or before the deadline turn.

The simulation is pure: given the temporal spec and the agent's per-turn actions, it produces the
same timeline and verdict every time — which is what makes it usable as a certification signal.
"""

from __future__ import annotations

TEMPORAL_KINDS = ("delayed", "async")


def _normalize_events(events: list[dict]) -> list[dict]:
    out: list[dict] = []
    for e in events:
        out.append(
            {
                "at_turn": int(e.get("at_turn", 0)),
                "kind": e.get("kind", "delayed") if e.get("kind") in TEMPORAL_KINDS else "delayed",
                "description": str(e.get("description", "")),
            }
        )
    return sorted(out, key=lambda e: e["at_turn"])


def _defused_turn(bomb: dict, agent_turns: list[str]) -> int | None:
    """First turn (<= deadline) whose agent action contains the defuse keyword, else None."""
    defuse = str(bomb.get("defuse", "")).lower().strip()
    deadline = int(bomb.get("deadline_turn", 0))
    if not defuse:
        return None
    for turn_idx, action in enumerate(agent_turns):
        if turn_idx > deadline:
            break
        if defuse in str(action).lower():
            return turn_idx
    return None


def simulate(events: list[dict], time_bombs: list[dict], agent_turns: list[str]) -> dict:
    """Run the temporal simulation and score it.

    - `agent_turns[i]` is the agent's action text on turn i.
    - Each scheduled event fires on its `at_turn`.
    - Each time-bomb detonates unless defused on or before `deadline_turn`.
    """
    norm_events = _normalize_events(events)
    horizon = max(
        [len(agent_turns) - 1]
        + [e["at_turn"] for e in norm_events]
        + [int(b.get("deadline_turn", 0)) for b in time_bombs],
        default=0,
    )

    timeline: list[dict] = []
    for turn in range(horizon + 1):
        fired = [e for e in norm_events if e["at_turn"] == turn]
        action = agent_turns[turn] if turn < len(agent_turns) else None
        if fired or action is not None:
            timeline.append(
                {
                    "turn": turn,
                    "events": [{"kind": e["kind"], "description": e["description"]} for e in fired],
                    "agent_action": action,
                }
            )

    bomb_results: list[dict] = []
    for bomb in time_bombs:
        defused_at = _defused_turn(bomb, agent_turns)
        detonated = defused_at is None
        bomb_results.append(
            {
                "deadline_turn": int(bomb.get("deadline_turn", 0)),
                "defuse": bomb.get("defuse", ""),
                "consequence": bomb.get("consequence", ""),
                "status": "detonated" if detonated else "defused",
                "defused_turn": defused_at,
            }
        )

    detonations = [b for b in bomb_results if b["status"] == "detonated"]
    total_bombs = len(bomb_results)
    realism_score = 1.0 if total_bombs == 0 else (total_bombs - len(detonations)) / total_bombs
    return {
        "horizon": horizon,
        "timeline": timeline,
        "time_bombs": bomb_results,
        "detonations": len(detonations),
        "realism_score": round(realism_score, 3),
        "passed": len(detonations) == 0,
    }
