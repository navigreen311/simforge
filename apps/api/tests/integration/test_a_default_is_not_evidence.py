"""ADR-0106 — a test that would pass on its own fallback tests nothing.

`test_a_pass_carries_its_basis.py` asserted `identity["settings"]["temperature"] == 0.0`, and
`DEFAULT_TEMPERATURE` is `0.0`. So the assertion held whether the declared value had travelled or
the runtime had fallen back to its own default. `test_operation_battery_run.py` was worse: it
asserted `{"temperature": 0.0, "max_tokens": 2048}` — **both** values equal to both defaults, on a
path whose whole point is that the Village's declaration was read.

Neither test was wrong about the value. Both were unable to tell the mechanism from its absence.

The fix is a value no default can produce, and the guard is what keeps it that way.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.services.agent_runtime.runtime import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
from tests.integration.test_a_pass_carries_its_basis import LOCAL_IDENTITY
from tests.integration.test_operation_battery_run import EXAM_SETTINGS

TESTS = Path(__file__).resolve().parent.parent

#: The live Village declares these. A fixture matching them would pass by coincidence rather than
#: by mechanism, which is the same defect wearing production's clothes.
PRODUCTION_SETTINGS = {"temperature": 0.7, "max_tokens": 4000}


def test_the_battery_fixture_declares_what_no_default_produces() -> None:
    assert EXAM_SETTINGS["temperature"] != DEFAULT_TEMPERATURE
    assert EXAM_SETTINGS["max_tokens"] != DEFAULT_MAX_TOKENS


def test_the_posted_identity_declares_what_no_default_produces() -> None:
    settings = LOCAL_IDENTITY["settings"]

    assert settings["temperature"] != DEFAULT_TEMPERATURE
    assert settings["max_tokens"] != DEFAULT_MAX_TOKENS


def test_neither_fixture_matches_production_either() -> None:
    """A value that happens to equal the live Village's would pass without the declaration being
    read too — the same blindness, one step further out."""
    for settings in (EXAM_SETTINGS, LOCAL_IDENTITY["settings"]):
        assert settings != PRODUCTION_SETTINGS
        assert (settings["temperature"], settings["max_tokens"]) != (
            PRODUCTION_SETTINGS["temperature"],
            PRODUCTION_SETTINGS["max_tokens"],
        )


def test_no_test_asserts_a_generation_setting_at_its_own_default() -> None:
    """**The sweep, made permanent.**

    A one-off grep finds today's instances; this fails the day another one is written. Scoped to
    the two generation settings, because that is where the shape actually bites: `temperature` and
    `max_tokens` both have a silent module-level fallback, so an assertion at the fallback's value
    proves nothing about what was declared.

    Deliberately NOT a scan for every literal equal to every default. `min_per_cell == 3` and
    `locale == "en"` also match defaults, and both are correct — those tests assert the default ON
    PURPOSE and nothing declared a competing value. The shape is narrower than the coincidence.
    """
    patterns = (
        (re.compile(r"temperature\"?\]?\s*==\s*0\.0(?![\d])"), "DEFAULT_TEMPERATURE"),
        (re.compile(r"max_tokens\"?\]?\s*==\s*2048(?![\d])"), "DEFAULT_MAX_TOKENS"),
        (re.compile(r'\{\s*"temperature":\s*0\.0\s*,\s*"max_tokens":\s*2048\s*\}'), "both"),
    )
    offenders: list[str] = []
    for path in sorted(TESTS.rglob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.lstrip().startswith("assert"):
                continue
            for pattern, which in patterns:
                if pattern.search(line):
                    rel = path.relative_to(TESTS).as_posix()
                    offenders.append(f"{rel}:{number} asserts {which} at its own value")

    assert offenders == [], (
        "a test asserts a generation setting at the value the runtime would have produced anyway, "
        "so it cannot tell a declared setting from a fallback (ADR-0106): " + "; ".join(offenders)
    )
