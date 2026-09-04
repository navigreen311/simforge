"""The outbound verdict vocabulary: what SimForge tells The Office about a run.

TWO VOCABULARIES, ON PURPOSE
============================

    SimForge stores STATES (`state_machine.OperationState`) — what a unit's
    certification *is*. The Office reads VERDICTS — what a *run* concluded. They are
    close enough to be confused and must not be merged: a state outlives the run that
    produced it, and two of the verdicts here (`TIMEOUT`, `IN_PROGRESS`) describe a run
    that produced no state at all.

    That gap is precisely the bug this module exists to close. SimForge's outbound shape
    carried states only, so a run that did not finish had nothing to say — and The
    Office's `VERDICT_TO_STATE[TIMEOUT] -> in_training`, which is correct, was
    unreachable.

THE TABLE IS THE CONTRACT
=========================

    `GATE_VERDICT_TO_STATE` below is the SimForge-side copy of
    `broker/certification.py:VERDICT_TO_STATE`. Neither side imports the other; both are
    asserted against `docs/contracts/office-simforge-contract.json` in
    `tests/contract/test_office_vocabulary_contract.py`. Adding a verdict in one place
    and not the other fails there.
"""

from __future__ import annotations

from enum import StrEnum

from src.services.operation.state_machine import OperationState


class GateVerdict(StrEnum):
    """Every verdict `GET /operation/gate-result/{run_ref}` may return."""

    PASS = "PASS"
    PROVISIONAL = "PROVISIONAL"
    FAIL = "FAIL"
    #: Observed by SimForge exceeding its own window. NEVER resolves to PASS (Part 10.1).
    TIMEOUT = "TIMEOUT"
    #: No run exists for this ref. A real absence, not a bad score.
    NOT_RUN = "NOT_RUN"
    #: Open and still inside its window. Has no outcome yet, and claiming one either way
    #: would be an invention.
    IN_PROGRESS = "IN_PROGRESS"
    REVOKED = "REVOKED"


#: The verdict → state table, SimForge's copy. Mirrors The Office's `VERDICT_TO_STATE`.
GATE_VERDICT_TO_STATE: dict[str, str] = {
    GateVerdict.PASS.value: OperationState.CERTIFIED.value,
    GateVerdict.PROVISIONAL.value: OperationState.PROVISIONAL.value,
    GateVerdict.FAIL.value: OperationState.FAILED.value,
    # A run that was cut off proved nothing about the agent: not a failure, not a pass.
    GateVerdict.TIMEOUT.value: OperationState.IN_TRAINING.value,
    GateVerdict.NOT_RUN.value: OperationState.NEVER_CERTIFIED.value,
    GateVerdict.IN_PROGRESS.value: OperationState.IN_TRAINING.value,
    GateVerdict.REVOKED.value: OperationState.REVOKED.value,
}

#: The inverse, for the states a FINISHED run can leave behind. Deliberately NOT the
#: full inverse of the table above: `in_training` maps back to two verdicts (TIMEOUT and
#: IN_PROGRESS) that mean different things, and which one applies is decided by the run's
#: clock in `run_window`, never by a lookup.
_FINISHED_STATE_TO_VERDICT: dict[str, str] = {
    OperationState.CERTIFIED.value: GateVerdict.PASS.value,
    OperationState.PROVISIONAL.value: GateVerdict.PROVISIONAL.value,
    OperationState.FAILED.value: GateVerdict.FAIL.value,
    OperationState.REVOKED.value: GateVerdict.REVOKED.value,
}


def verdict_for_finished_state(state: str) -> str:
    """The verdict a run that PRODUCED `state` reports.

    A stale state (`stale_instructions` / `stale_forge`) is not a run outcome — it is
    something that happened to a cert afterwards — so it never reaches here. Anything
    unmapped raises rather than defaulting: a silent default in this table is how a
    non-outcome would become a PASS.
    """
    try:
        return _FINISHED_STATE_TO_VERDICT[state]
    except KeyError:
        raise ValueError(
            f"{state!r} is not a state a finished operation run can produce. "
            f"Runs produce {sorted(_FINISHED_STATE_TO_VERDICT)}; a stale or in-training "
            "state is not a run outcome and must not be reported as one."
        ) from None


def is_assignable_verdict(verdict: str) -> bool:
    """Only PASS permits a Forge call. Stated as its own function so the TIMEOUT rule is
    checkable directly: `is_assignable_verdict("TIMEOUT")` is False, always."""
    return GATE_VERDICT_TO_STATE.get(verdict) == OperationState.CERTIFIED.value


#: Weakest to strongest, for collapsing a run that certified several units into the ONE
#: verdict The Office reads per `run_ref`. Order matters: `revoked` is the strongest
#: claim against a run and therefore the weakest outcome.
_STATE_STRENGTH: tuple[str, ...] = (
    OperationState.REVOKED.value,
    OperationState.FAILED.value,
    OperationState.PROVISIONAL.value,
    OperationState.CERTIFIED.value,
)


def weakest_state(states: list[str]) -> str | None:
    """The state a multi-unit run reports as a whole. None for an empty run.

    Weakest wins. A run that certified four agents and failed the fifth is not a PASS —
    reporting it as one is the "looks like success" failure the whole contract exists to
    prevent, and the Office reads a single verdict per `run_ref` with no room to qualify
    it. States outside the finished set are ignored rather than ranked: they are not run
    outcomes.
    """
    ranked = [s for s in states if s in _STATE_STRENGTH]
    if not ranked:
        return None
    return min(ranked, key=_STATE_STRENGTH.index)
