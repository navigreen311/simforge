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
    - ADR-0143: on a partition sealed under rule 2, one agent's FAIL rows
      read as PASS when they are slips only and total one at most
      (`partition_tolerance.fold_agent`). The rows still say FAIL.
    - Sealed with no matching verdict: NOT_RUN, `decided_at` null.
    - No sealed partition, or an unknown venture: false / null / null.
      The two are indistinguishable by design.
    - ADR-0148: a sealed partition whose recorded instruction hashes no
      longer match the live sets answers NOT_RUN, `decided_at` null, until a
      new partition is sealed. Its scenarios number rules that moved, so its
      verdicts describe instructions no longer in force - the same reason
      the grader refuses to put it (ADR-0125).

Pure read. No flush, no cache: every call asks the database.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.held_out_partition import HeldOutPartition, HeldOutPartitionVerdict
from src.services.operation.live_instructions import live_sets
from src.services.operation.partition_tolerance import fold_agent
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION, PARTITION_PROTOCOL_VERSION

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
    # Only these are selected. Nothing else about it leaves here, and none of it is scenario
    # content: the hashes are the instruction sets' own identities (ADR-0125).
    row = (
        await session.execute(
            select(
                HeldOutPartition.id,
                HeldOutPartition.contentDigest,
                HeldOutPartition.verdictRule,
                HeldOutPartition.forgeId,
                HeldOutPartition.instructionHashes,
            )
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

    partition_id, digest, rule, forge_id, authored_from = partition
    # ADR-0148. Before any verdict is read: a partition authored from instructions that are no
    # longer live answers nothing about the agents operating the live ones. Null hashes predate
    # ADR-0125; such a partition is never graded and its sittings are not current, so it already
    # reads NOT_RUN below.
    if authored_from and await _instructions_moved(session, forge_id, authored_from):
        return _answer(venture_id, True, "NOT_RUN", None)
    rows = (
        await session.execute(
            select(
                HeldOutPartitionVerdict.agentId,
                HeldOutPartitionVerdict.verdict,
                HeldOutPartitionVerdict.decidedAt,
                HeldOutPartitionVerdict.slipCount,
            )
            .where(HeldOutPartitionVerdict.partitionId == partition_id)
            .where(HeldOutPartitionVerdict.partitionDigest == digest)
            # ADR-0122: only sittings under the current protocol are evidence. One under a
            # superseded version - or written before the version was recorded - is history.
            .where(HeldOutPartitionVerdict.protocolVersion == PARTITION_PROTOCOL_VERSION)
            # ADR-0137. And under the current rubric: one graded by another rule is history.
            .where(HeldOutPartitionVerdict.rubricVersion == OPERATION_RUBRIC_VERSION)
            # Newest first; ULID ids break a decidedAt tie in insert order.
            .order_by(
                HeldOutPartitionVerdict.decidedAt.desc(),
                HeldOutPartitionVerdict.id.desc(),
            )
        )
    ).all()

    # ADR-0121: the weakest sitting, not the latest. Every final row counts, so the
    # weakest over them is the weakest over sittings; an IN_PROGRESS counts only while
    # it is the agent's newest row - once its seed has a final row it is superseded.
    latest: dict[str, tuple[str, datetime]] = {}
    newest_seen: set[str] = set()
    candidates: dict[str, list[tuple[str, datetime, int | None]]] = {}
    for agent_id, verdict, decided_at, slips in rows:
        first = agent_id not in newest_seen
        newest_seen.add(agent_id)
        if verdict == "IN_PROGRESS" and not first:
            continue
        candidates.setdefault(agent_id, []).append((verdict, decided_at, slips))
    for agent_id, items in candidates.items():
        # ADR-0143. Under the partition's rule. A tolerated slip turns its FAIL rows to PASS
        # here and only here; the rows themselves still say FAIL.
        folded = fold_agent([(v, s) for v, _, s in items], rule)
        effective = [("PASS" if v == "FAIL" and folded.tolerated else v, d) for v, d, _ in items]
        latest[agent_id] = min(effective, key=lambda it: (_RANK.get(it[0], -1), -_as_ts(it[1])))

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


async def _instructions_moved(
    session: AsyncSession, forge_id: str, authored_from: dict[str, str]
) -> bool:
    """Any module whose live instruction set is not the one the partition was authored from."""
    live = await live_sets(session, forge_id)
    return any(m not in live or live[m].contentHash != h for m, h in authored_from.items())


def _as_ts(dt: datetime) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()
