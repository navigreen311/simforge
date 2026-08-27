"""Composed operation-cert views (Batch 6): side-by-side, coverage, capacity, dept-context."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cert import AgentCert
from src.models.operation_cert import OperationCertification
from src.utils.time import utcnow


async def _seed(session: AsyncSession) -> str:
    agent = (
        await session.execute(select(Agent).where(Agent.villageAgentId == "taylor_zhang"))
    ).scalar_one()
    # A domain cert (record 1, shown beside the operation cert — never merged).
    session.add(
        AgentCert(
            agentId=agent.id,
            forgeCap="capital-forge.statement_ingest",
            tier="foundational",
            status="active",
            issuedAt=utcnow(),
            expiresAt=utcnow(),
            certSnapshotId="cs-op-view",
        )
    )
    # An operation cert (record 2), Unit A, with its own denominator + named-list + version stamp.
    session.add(
        OperationCertification(
            unitType="agent_operation",
            state="certified",
            forgeId="capital-forge",
            agentId=agent.id,
            moduleId="statement_ingest",
            instructionVersion="1.2.0",
            forgeApiVersion="3.0.0",
            instructionContentHash="hash-abc",
            operationRubricVersion="0.1.0",
            functionsCertified=11,
            functionsInModule=14,
            maxCertifiedTrustTier="propose",
            operationRubricResults=[
                {"dimension": "sequence_correctness", "verdict": "PASS", "score": 0.9},
                {"dimension": "never_do_adherence", "verdict": "NOT_APPLICABLE"},
            ],
            rubricDimensionSpread=0.15,
            perScenarioClass={"happy_path": "PASS"},
            failureModesObserved=[],
        )
    )
    await session.commit()
    return agent.villageAgentId


async def test_side_by_side_pairs_domain_and_operation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    vid = await _seed(db_session)
    res = (await client.get("/api/operation/side-by-side")).json()
    # Two SEPARATE version stamps, never one number.
    assert res["operation_rubric_version"] == "0.1.0"
    assert res["domain_rubric_version"] == "1.0.0"
    item = next(i for i in res["items"] if i["agent_village_id"] == vid)
    # Operation record carries its OWN denominator + named list.
    assert item["operation"]["functions_certified"] == 11
    assert item["operation"]["functions_in_module"] == 14
    assert item["operation"]["operation_rubric_version"] == "0.1.0"
    assert isinstance(item["operation"]["operation_rubric_results"], list)
    # Domain record is present, separate, with its OWN version stamp — not merged.
    assert item["domain"]["present"] is True
    assert item["domain"]["rubric_version"] == "1.0.0"
    assert item["domain"]["tier"] == "foundational"
    # No merged score anywhere.
    assert "score" not in item


async def test_domain_certified_operation_uncertified_is_normal(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # An agent with a domain cert but NO operation cert must not appear as an operation failure —
    # side-by-side only lists operation certs; the absence is a calm never_certified in the UI.
    res = (await client.get("/api/operation/side-by-side")).json()
    assert res["items"] == []  # nothing seeded → empty, not an error


async def test_coverage_and_capacity_and_dept_shapes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    cov = (await client.get("/api/operation/coverage")).json()
    forge = next(f for f in cov["forges"] if f["forge_id"] == "capital-forge")
    mod = next(m for m in forge["modules"] if m["module_id"] == "statement_ingest")
    # FIX 3 — module coverage is NOT one agent's denominator: it reports the module denominator,
    # certified-agent count, and the best single agent as an explicit union lower bound.
    assert mod["functions_in_module"] == 14
    assert mod["certified_agents"] == 1
    assert mod["best_single_agent_functions"] == 11
    assert "functions_covered" not in mod  # the conflated field is gone
    assert "coverage_note" in cov

    cap = (await client.get("/api/operation/capacity-view")).json()
    assert cap["totals"]["certified_free"] == 1
    assert cap["totals"]["produced_not_certified"] == 0

    dept = (await client.get("/api/operation/dept-context")).json()
    assert dept["total"] == 0  # only Unit A seeded
