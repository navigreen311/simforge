"""ADR-0101 — timestamps are stored one way across the service, and the exam publishes its versions.

Two defects, one turn, and the first one hid the second.

**The clock.** 108 timestamp columns in this schema are `timestamp without time zone` and hold
naive UTC. Three of ours were `timestamp with time zone`, from one hand-written migration. The ORM
writes a naive UTC datetime; Postgres reads a naive literal against a timestamptz column in the
SESSION zone — `America/Los_Angeles` here — so 04:50 UTC was stored as 04:50 PDT, which is 11:50
UTC. Seven hours late, no error, and correct-looking to anyone who prints the column in UTC.

**It made forensics lie.** Forty-four rows were reported as a curriculum rewritten six hours after
a sweep. They were written thirty minutes before it, in the same Gate 8 pass that opened the runs
that sweep graded.

**The versions.** The Office mints a run ref from the exam's identity and now puts both versions in
it. Neither was published, so `assign_contract` minted the same ref across two protocol MAJORs and
a rubric bump, `open_run` returned the closed run, and it could not be re-examined at all.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from src.models.base import _now
from src.services.operation.battery import RESPONSE_PROTOCOL_VERSION as FROM_BATTERY
from src.services.operation.rubric import (
    OPERATION_RUBRIC_VERSION,
    RESPONSE_PROTOCOL_VERSION,
)

MIGRATIONS = Path(__file__).resolve().parents[4] / "packages" / "db" / "migrations"
#: The one migration that introduced a tz-aware column, and the one that reverses it. Named so the
#: scan below can say "only these two", which is a stronger statement than "some".
_INTRODUCED = "20260918000000_the_answer_key_is_kept"
_REVERSED = "20260921180000_one_clock"


# =================================================================================================
# One clock
# =================================================================================================


def test_now_is_naive_and_utc() -> None:
    """`_now` already documents the convention: *naive UTC — matches Prisma `timestamp` columns;
    avoids asyncpg local-time shift.* The column that broke was the one that did not match it."""
    value = _now()

    assert isinstance(value, datetime)
    assert value.tzinfo is None, "a tz-aware value against a naive column is the other half of this"
    assert abs((value - datetime.now(UTC).replace(tzinfo=None)).total_seconds()) < 5


def test_no_migration_introduces_a_tz_aware_column_any_more() -> None:
    """**The convention, pinned where it can be broken.**

    A scan rather than a schema assertion, because the schema is not in this repository's test
    database — the suite runs on SQLite, where `TIMESTAMPTZ` and `TIMESTAMP` are the same word.
    The migrations are the only place the distinction is written down, so they are where it is
    held.
    """
    pattern = re.compile(r"TIMESTAMPTZ|WITH TIME ZONE", re.IGNORECASE)
    offenders = {
        path.parent.name
        for path in MIGRATIONS.glob("*/migration.sql")
        # A `--` comment line may discuss the type; only real SQL counts.
        if any(
            pattern.search(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if not line.strip().startswith("--")
        )
    }

    assert offenders <= {_INTRODUCED, _REVERSED}, (
        f"a migration introduced a tz-aware column: {sorted(offenders - {_INTRODUCED, _REVERSED})}"
    )
    assert _INTRODUCED in offenders, (
        "the positive control: the migration that caused this is still there"
    )


def test_the_repair_is_the_inverse_of_the_damage_not_a_utc_cast() -> None:
    """`AT TIME ZONE 'UTC'` would preserve the seven-hour error and call it corrected. The damage
    was *read this naive value as America/Los_Angeles*, so the repair is *render it back in
    America/Los_Angeles and keep the wall clock*."""
    sql = (MIGRATIONS / _REVERSED / "migration.sql").read_text(encoding="utf-8")
    statements = "\n".join(
        line for line in sql.splitlines() if not line.strip().startswith("--")
    )

    assert "AT TIME ZONE 'America/Los_Angeles'" in statements
    assert "USING (\"createdAt\" AT TIME ZONE 'UTC')" not in statements


# =================================================================================================
# The exam publishes its versions
# =================================================================================================


def test_the_protocol_version_lives_where_a_router_may_reach_it() -> None:
    """ADR-0050 forbids a request handler reaching the held-out corpus, and
    `test_the_router_cannot_reach_the_battery` walks the graph to prove it. `/api/version` has to
    publish this string, so the string could not stay beside the probes. `battery` re-exports it
    and still owns the TEXT."""
    assert RESPONSE_PROTOCOL_VERSION == FROM_BATTERY
    assert RESPONSE_PROTOCOL_VERSION == "6.0.0"
    assert OPERATION_RUBRIC_VERSION == "0.5.0"
