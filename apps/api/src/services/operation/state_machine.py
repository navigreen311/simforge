"""The 7-state operation-cert state machine (Batch 2).

The states are DISTINCT and must never be collapsed into one another or reported as a "low score":
a run that never happened (never_certified) is NOT a run that scored badly (failed), and neither is
a cert gone stale. Keeping these apart is the whole point of the not-run-vs-failed invariant.

Separate from the domain cert status enum (active|expired|revoked|suspended) — do not reuse it.
"""

from __future__ import annotations

from enum import StrEnum


class OperationState(StrEnum):
    # Earned and current — the ONLY assignable state.
    CERTIFIED = "certified"
    # Instructions rewritten since the cert was earned → not assignable, re-cert required.
    STALE_INSTRUCTIONS = "stale_instructions"
    # Forge released a version affecting this module → not assignable, re-cert required.
    STALE_FORGE = "stale_forge"
    # Actively running an operation battery toward a cert.
    IN_TRAINING = "in_training"
    # Never run for this unit — a real absence, NOT a bad score. Distinct from `failed`.
    NEVER_CERTIFIED = "never_certified"
    # Ran and did not pass. Distinct from `never_certified` and from a low score in results.
    FAILED = "failed"
    # Voided (e.g. content-hash mismatch, drift, misoperation incident) — not assignable.
    REVOKED = "revoked"


OPERATION_STATES: tuple[str, ...] = tuple(s.value for s in OperationState)

# Legal state transitions. A brand-new unit starts at never_certified; running a battery moves it to
# in_training; the outcome is certified or failed. Stale/revoked are re-cert entry points back into
# in_training. Terminal-ish states still allow a fresh battery (in_training) — nothing is a dead end
# except by policy.
LEGAL_TRANSITIONS: dict[OperationState, frozenset[OperationState]] = {
    OperationState.NEVER_CERTIFIED: frozenset({OperationState.IN_TRAINING}),
    OperationState.IN_TRAINING: frozenset(
        {OperationState.CERTIFIED, OperationState.FAILED}
    ),
    OperationState.CERTIFIED: frozenset(
        {
            OperationState.STALE_INSTRUCTIONS,
            OperationState.STALE_FORGE,
            OperationState.REVOKED,
        }
    ),
    OperationState.STALE_INSTRUCTIONS: frozenset(
        {OperationState.IN_TRAINING, OperationState.REVOKED}
    ),
    OperationState.STALE_FORGE: frozenset(
        {OperationState.IN_TRAINING, OperationState.REVOKED}
    ),
    OperationState.FAILED: frozenset({OperationState.IN_TRAINING}),
    OperationState.REVOKED: frozenset({OperationState.IN_TRAINING}),
}


def _coerce(state: str | OperationState) -> OperationState:
    return state if isinstance(state, OperationState) else OperationState(state)


def is_transition_legal(
    from_state: str | OperationState, to_state: str | OperationState
) -> bool:
    """True if `from_state` → `to_state` is an allowed transition."""
    return _coerce(to_state) in LEGAL_TRANSITIONS.get(_coerce(from_state), frozenset())


def is_assignable(state: str | OperationState) -> bool:
    """Only a `certified` unit is assignable to a shift. Stale/failed/never/revoked/in_training are
    all NOT assignable — each for a distinct reason, never conflated into a low score."""
    return _coerce(state) is OperationState.CERTIFIED


def is_recert_required(state: str | OperationState) -> bool:
    """Stale states (instructions rewritten or Forge released) require re-cert. Distinct from a
    never_certified unit (which was never run) and a failed one (which ran and did not pass)."""
    return _coerce(state) in (
        OperationState.STALE_INSTRUCTIONS,
        OperationState.STALE_FORGE,
    )
