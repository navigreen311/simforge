"""Integrated-execution triple gate — off by default (ADR-0025)."""

from __future__ import annotations

import pytest

from src.config import settings
from src.services.execution import is_integrated_enabled


@pytest.mark.parametrize(
    ("flag", "pack_allows", "requested", "expected"),
    [
        (False, True, True, False),  # global flag off → never integrated
        (True, False, True, False),  # pack didn't opt in → never
        (True, True, False, False),  # run didn't request it → never
        (True, True, True, True),  # all three agree → integrated
        (False, False, False, False),
    ],
)
def test_triple_gate(
    monkeypatch: pytest.MonkeyPatch, flag: bool, pack_allows: bool, requested: bool, expected: bool
) -> None:
    monkeypatch.setattr(settings, "integrated_execution_enabled", flag)
    assert is_integrated_enabled(pack_allows, requested) is expected


def test_default_is_off() -> None:
    # The shipped default must be off — no integrated execution without an explicit opt-in.
    assert settings.integrated_execution_enabled is False
