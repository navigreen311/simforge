"""Dress Rehearsal Protocol (§15) — gated go-live entry/exit criteria + signed sign-offs."""

from src.services.rehearsal.protocol import (
    RehearsalError,
    check_entry_criteria,
    check_exit_criteria,
    run_exit,
    sign_off,
    start_rehearsal,
)

__all__ = [
    "RehearsalError",
    "check_entry_criteria",
    "check_exit_criteria",
    "start_rehearsal",
    "run_exit",
    "sign_off",
]
