"""Human Operating Model (§11.8): queues, SLA engine, role inboxes, ownership matrix, handoff."""

from __future__ import annotations

from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.gap import SoftwareGap
from src.utils.time import utcnow


async def test_ownership_matrix_and_empty_board(client: AsyncClient) -> None:
    matrix = (await client.get("/api/ops/matrix")).json()["matrix"]
    names = {m["queue"] for m in matrix}
    assert {"gaps_p0", "cert_reviews", "appeal_cases", "regression_alerts"} <= names
    # Every queue has an owner, backup, role, SLA.
    for m in matrix:
        assert m["owner"] and m["backup"] and m["role"] and m["sla_hours"] > 0
    # Empty board is healthy.
    board = (await client.get("/api/ops/board")).json()
    assert board["health"] == "ok" and board["total_open"] == 0


_GAP_SEQ = [0]


async def _seed_gap(session: AsyncSession, severity: str, age_hours: float) -> None:
    _GAP_SEQ[0] += 1
    n = _GAP_SEQ[0]
    gap = SoftwareGap(
        ticketId=f"SF-GAP-{n}-{severity}-{int(age_hours * 10)}",
        runId="run-fake",
        forge="cre-forge",
        module="call_center",
        severity=severity,
        summary=f"{severity} gap aged {age_hours}h",
        detail="x",
        status="open",
        firstSeenRunId="run-fake",
        lastSeenRunId="run-fake",
    )
    session.add(gap)
    await session.flush()
    gap.createdAt = utcnow() - timedelta(hours=age_hours)
    await session.commit()


async def test_sla_status_within_at_risk_breached(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # P0 SLA is 4h: 1h → within, 3.5h → at_risk (≥75%), 5h → breached.
    await _seed_gap(db_session, "P0", 1)
    await _seed_gap(db_session, "P0", 3.6)
    await _seed_gap(db_session, "P0", 5)
    board = (await client.get("/api/ops/board")).json()
    p0 = next(q for q in board["queues"] if q["name"] == "gaps_p0")
    statuses = sorted(i["sla_status"] for i in p0["items"])
    assert statuses == ["at_risk", "breached", "within"]
    assert p0["breached"] == 1 and p0["at_risk"] == 1
    assert board["health"] == "breached" and board["total_breached"] == 1


async def test_role_inbox_scopes_to_owned_queues(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_gap(db_session, "P1", 1)
    inbox = (await client.get("/api/ops/inbox/sre")).json()
    assert inbox["role"] == "sre"
    qnames = {q["name"] for q in inbox["queues"]}
    assert qnames == {"gaps_p0", "gaps_p1", "gaps_p2"}  # SRE owns the gap queues only
    assert inbox["open"] == 1


async def test_handoff_reports_breaches_and_safe_modes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_gap(db_session, "P0", 10)  # breached
    await client.post(
        "/api/constitution/safe-mode",
        json={"active": True, "scope_type": "forge", "scope_value": "voiceforge", "reason": "x"},
    )
    handoff = (await client.get("/api/ops/handoff")).json()
    assert handoff["health"] == "breached"
    assert handoff["queue_counts"]["gaps_p0"]["breached"] == 1
    assert len(handoff["sla_breaches_read_back"]) == 1
    assert "forge:voiceforge" in handoff["active_safe_modes"]
