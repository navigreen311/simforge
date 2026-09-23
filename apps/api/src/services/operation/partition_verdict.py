"""Gate 9.5's answer to The Office: whether, never why (ADR-0111).

The shape is fixed by `docs/contracts/gate-9-5-verdict.md`. Four keys, always:
`venture_id`, `partition_exists`, `verdict`, `decided_at`. Nothing else.

WHAT THIS READS, AND WHAT IT MAY NEVER READ
===========================================

    `HeldOutPartition` (which one is sealed, and its digest) and
    `HeldOutPartitionVerdict` (who was graded, and how). Nothing more.

    It never touches `HeldOutPartitionScenario`. A function that never
    held a scenario cannot leak one, whatever is later written in it.
    That is a stronger control than a careful function (ADR-0050).

    It does not import the authoring or grading services either. They
    hold content; this is on a request path.

THE RULES, FROM THE CONTRACT TABLE
==================================

    - Only the currently sealed partition counts.
    - Per agent, only the latest verdict whose `partitionDigest` equals
      that partition's `contentDigest`. A stale digest is ignored.
    - Weakest wins: FAIL < TIMEOUT < IN_PROGRESS < NOT_RUN < PASS.
    - Sealed with no matching verdict: NOT_RUN, `decided_at` null.
    - No sealed partition, or an unknown venture: false / null / null.
      The two are indistinguishable by design.

Pure read. No flush, no cache: every call asks the database.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.held_out_partition import HeldOutPartition, HeldOutPartitionVerdict

#: Weakest first. Any non-PASS blocks; the order only picks which one is named.
WEAKNESS_ORDER: tuple[str, ...] = ("FAIL", "TIMEOUT", "IN_PROGRESS", "NOT_RUN", "PASS")
_RANK = {v: i for i, v in enumerate(WEAKNESS_ORDER)}

#: The four keys, in contract order. The response model enforces the same set.
RESPONSE_KEYS: tuple[str, ...] = ("venture_id", "partition_exists", "verdict", "decided_at")


def _iso_utc(dt: datetime) -> str:
    # Persisted timestamps are naive UTC (src/utils/time.py). Say so on the wire.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _answer(
    venture_id: str, exists: bool, verdict: str | None, decided_at: str | None
) -> dict[str, Any]:
    return dict(zip(RESPONSE_KEYS, (venture_id, exists, verdict, decided_at), strict=True))


async def _sealed_partition(session: AsyncSession, venture_id: str):
    # Only the id and digest are selected. Nothing else about it leaves here.
    row = (
        await session.execute(
            select(HeldOutPartition.id, HeldOutPartition.contentDigest)
            .where(HeldOutPartition.ventureId == venture_id)
            .where(HeldOutPartition.status == "sealed")
            .order_by(HeldOutPartition.sealedAt.desc(), HeldOutPartition.id.desc())
            .limit(1)
        )
    ).first()
    return row


async def venture_verdict(session: AsyncSession, venture_id: str) -> dict[str, Any]:
    """The contract's four keys for one venture. See the module docstring."""
    partition = await _sealed_partition(session, venture_id)
    if partition is None:
        return _answer(venture_id, False, None, None)

    partition_id, digest = partition
    rows = (
        await session.execute(
            select(
                HeldOutPartitionVerdict.agentId,
                HeldOutPartitionVerdict.verdict,
                HeldOutPartitionVerdict.decidedAt,
            )
            .where(HeldOutPartitionVerdict.partitionId == partition_id)
            .where(HeldOutPartitionVerdict.partitionDigest == digest)
            # Newest first; ULID ids break a decidedAt tie in insert order.
            .order_by(
                HeldOutPartitionVerdict.decidedAt.desc(),
                HeldOutPartitionVerdict.id.desc(),
            )
        )
    ).all()

    latest: dict[str, tuple[str, datetime]] = {}
    for agent_id, verdict, decided_at in rows:
        latest.setdefault(agent_id, (verdict, decided_at))

    if not latest:
        return _answer(venture_id, True, "NOT_RUN", None)

    # Weakest verdict; among equals, the most recent decision. An unknown
    # verdict string ranks weakest of all and is reported as FAIL: a value
    # the contract does not name must never read as a pass.
    def key(item: tuple[str, datetime]) -> tuple[int, float]:
        verdict, decided_at = item
        return (_RANK.get(verdict, -1), -_as_ts(decided_at))

    verdict, decided_at = min(latest.values(), key=key)
    if verdict not in _RANK:
        verdict = "FAIL"
    return _answer(venture_id, True, verdict, _iso_utc(decided_at))


def _as_ts(dt: datetime) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()
