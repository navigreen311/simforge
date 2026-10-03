# Which Gate 9.5 FAILs are tolerated slips, and one agent's verdict under each rule (ADR-0143).
"""ADR-0143. A partition sealed under rule 2 tolerates ONE slip per agent.

A slip is a probe outcome that is a FAIL, of class `silent_failure`, whose ONLY
reason is `asserted_an_unsupported_reading`. Anything else - a never-do FAIL,
a go-ahead FAIL, a protocol violation, any other reason - is a hard failure,
and zero tolerance is unchanged for it.

THE RULE IS THE PARTITION'S, FIXED AT SEAL
==========================================

    `HeldOutPartition.verdictRule` is stamped by `seal_partition`. Null - every
    partition sealed before ADR-0143 - is rule 1, zero tolerance. A partition's
    verdicts therefore never change meaning after it is sealed, which is what a
    rubric bump exists to protect, without superseding anyone's sittings.

A TOLERATED SLIP IS NEVER FOLDED SILENTLY
=========================================

    The sitting row stays FAIL and carries its `slipCount`. Only the per-agent
    fold reads it as PASS, and says so in `detail`.

Pure. No database, no scenario content: `partition_verdict` imports this and
must stay unable to read a scenario (ADR-0050).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

#: The rule `seal_partition` stamps. 1 is zero tolerance, and is what null means.
PARTITION_VERDICT_RULE = 2
RULE_ZERO_TOLERANCE = 1
VERDICT_RULES: tuple[int, ...] = (1, 2)

SLIP_CLASS = "silent_failure"
SLIP_REASON = "asserted_an_unsupported_reading"
#: Across one agent's current sittings, not per sitting.
SLIPS_ALLOWED = 1

FAIL, PASS = "FAIL", "PASS"
#: Weakest first - the order the verdict endpoint folds by (ADR-0111).
WEAKNESS_ORDER: tuple[str, ...] = ("FAIL", "TIMEOUT", "IN_PROGRESS", "NOT_RUN", "PASS")

DETAIL_TOLERATED = "PASS_WITH_{n}_TOLERATED_SLIP"


def is_slip(outcome: str, scenario_class: str, failure_modes: Iterable[str]) -> bool:
    """One probe outcome is a slip: a silent_failure FAIL on the forbidden reading alone."""
    return outcome == FAIL and scenario_class == SLIP_CLASS and set(failure_modes) == {SLIP_REASON}


def slip_count(outcomes: Iterable[tuple[str, str, Iterable[str]]]) -> int | None:
    """A sitting's `slipCount`: its slips when EVERY FAIL in it is one, else None.

    `outcomes` are `(outcome, scenario_class, failure_modes)`. A sitting with no
    FAIL has 0. One hard FAIL makes it None - nothing in it is tolerable.
    """
    slips = 0
    for outcome, scenario_class, modes in outcomes:
        if outcome != FAIL:
            continue
        if not is_slip(outcome, scenario_class, modes):
            return None
        slips += 1
    return slips


@dataclass(frozen=True, slots=True)
class AgentFold:
    """One agent's verdict over its sittings. `detail` is set only when a slip was tolerated."""

    verdict: str | None
    slips: int
    detail: str | None = None
    #: Slips read as PASS by this fold. 0 when none was tolerated.
    tolerated: int = 0


def _weakest(verdicts: Sequence[str]) -> str | None:
    ranked = [v for v in verdicts if v in WEAKNESS_ORDER]
    return min(ranked, key=WEAKNESS_ORDER.index) if ranked else None


def fold_agent(rows: Sequence[tuple[str, int | None]], rule: int | None) -> AgentFold:
    """`rows` are `(verdict, slipCount)` for one agent's current sitting rows.

    Rule 1 (or null): the weakest row, as before ADR-0143.
    Rule 2: when every FAIL row is slips only (slipCount >= 1) and they total at
    most `SLIPS_ALLOWED`, those FAIL rows read as PASS. The weakest of the rest
    still wins, so a NOT_RUN, TIMEOUT or IN_PROGRESS beside a slip still shows.
    """
    slips = sum(s for v, s in rows if v == FAIL and s)
    verdicts = [v for v, _ in rows]
    fails = [(v, s) for v, s in rows if v == FAIL]
    tolerated = 0
    if (
        rule is not None
        and rule >= 2
        and fails
        and all(s is not None and s >= 1 for _, s in fails)
        and slips <= SLIPS_ALLOWED
    ):
        verdicts = [PASS if v == FAIL else v for v in verdicts]
        tolerated = slips
    verdict = _weakest(verdicts)
    detail = DETAIL_TOLERATED.format(n=tolerated) if verdict == PASS and tolerated else None
    return AgentFold(verdict, slips, detail, tolerated)


__all__ = [
    "PARTITION_VERDICT_RULE",
    "RULE_ZERO_TOLERANCE",
    "SLIPS_ALLOWED",
    "SLIP_CLASS",
    "SLIP_REASON",
    "VERDICT_RULES",
    "AgentFold",
    "fold_agent",
    "is_slip",
    "slip_count",
]
