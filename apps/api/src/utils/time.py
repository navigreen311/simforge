"""Time helpers.

Prisma maps `DateTime` to Postgres `timestamp` (WITHOUT time zone), so writing tz-aware
values makes asyncpg shift them to local time on write. We standardize on **naive UTC**
for persisted timestamps so the stored instant equals the intended UTC instant — critical
for signed CertSnapshots, where the hashed value must survive a DB round-trip byte-for-byte.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Current time as a naive UTC datetime, truncated to milliseconds.

    Prisma maps `DateTime` to Postgres `timestamp(3)` (millisecond precision), which rounds
    microseconds on write. Truncating here makes the stored value equal the in-memory value,
    so signed CertSnapshots verify after a DB round-trip.
    """
    dt = datetime.now(UTC).replace(tzinfo=None)
    return dt.replace(microsecond=(dt.microsecond // 1000) * 1000)
