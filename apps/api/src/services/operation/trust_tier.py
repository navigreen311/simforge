"""The certified trust tier: a CEILING a battery may justify, never a score it measured.

WHAT THE TIER IS FOR
====================

The Office declares a tier for a position and caps it with what SimForge certified
(`broker/certification.py::cap_tier`, Part 10.1). A missing tier is not a soft default there:
`record_result` REFUSES to write a `certified` row without one, so a tier SimForge does not send is
a pass The Office cannot record.

WHY A BATTERY CANNOT REACH `auto_execute`, AND THAT THIS IS STRUCTURAL
=====================================================================

The held-out battery exercises OBLIGATIONS — did the agent decline the prohibited act, did it
conceal, did it answer in the declared grammar. It exercises no module function, which is why
`build_gate_result_request` carries `functions_certified = 0` and says so in as many words.

`auto_execute` is the tier that lets an agent complete an act unattended. Certifying it on a
battery that never watched the agent perform one would be a claim about work nobody observed —
the same error as inventing a coverage numerator, pointing the other way.

So the ceiling is `propose`, and **it is a ceiling rather than a measurement**. It does not move
with the score, it is the same value for a battery that passed eleven probes and one that passed
three, and nothing a battery of obligations can observe will raise it. Stated here, plainly,
because a constant that travels as though it were measured is a defect this repository has
produced five times (calibration entries 8–12) and the shape is always the same: a number nobody
computed, read later as evidence.

**Raising it needs a different battery**, one that runs the module's functions and can report a
real numerator — not a wider rule here.
"""

from __future__ import annotations

from src.services.operation.state_machine import OperationState

#: Weakest to strongest. The SimForge-side copy of `broker/certification.py:TIER_RANK`, asserted
#: against `docs/contracts/office-simforge-contract.json` in the vocabulary contract test — a tier
#: one side can send and the other cannot rank is an uncappable grant.
TRUST_TIERS: tuple[str, ...] = ("suggest", "propose", "auto_execute")

TIER_RANK: dict[str, int] = {tier: rank for rank, tier in enumerate(TRUST_TIERS, start=1)}

#: The strongest tier a held-out obligation battery justifies. See the module docstring: a ceiling,
#: not a measurement.
BATTERY_TIER_CEILING: str = "propose"


def weakest_tier(tiers: list[str | None]) -> str | None:
    """The tier a multi-unit run reports as a whole. `None` when nothing named one.

    Weakest wins, for the reason `weakest_state` gives: The Office reads ONE tier per `run_ref` and
    caps a declared tier with it, so a run that certified four units at `propose` and one at
    `suggest` must cap at `suggest`. Reporting the strongest would hand the weakest unit a grant
    its own battery never earned.

    Unknown values are ignored rather than ranked — a tier this side cannot rank is one The Office
    cannot cap against, and guessing where it sits would invent the grant.
    """
    ranked = [t for t in tiers if t in TIER_RANK]
    if not ranked:
        return None
    return min(ranked, key=lambda t: TIER_RANK[str(t)])


def tier_for_state(state: str, declared: str | None) -> str | None:
    """The tier a unit in `state` may carry. `None` for every state but `certified`.

    The cap is applied HERE rather than trusted from the outcome, because the outcome is written
    before the state is known: a battery declares the ceiling its exam can justify, and whether the
    unit reached it is decided by the gate-result path from the rubric, the spread and the
    coverage holes.

    `provisional` deliberately carries none. The Office's `record_result` requires no tier for a
    provisional row and its comment says why: certification was WITHHELD, so there is no certified
    tier, and a placeholder here is one a later reader takes for a real cap.
    """
    if state != OperationState.CERTIFIED.value:
        return None
    return declared if declared in TIER_RANK else None


__all__ = [
    "BATTERY_TIER_CEILING",
    "TIER_RANK",
    "TRUST_TIERS",
    "tier_for_state",
    "weakest_tier",
]
