"""ADR-0093 — a score that describes only the held-out half must say so.

Four certifications on 19 September read `score 1.0 / threshold 1.0` beside three competence
dimensions at FAIL. **The number was true.** Every held-out probe passed: three attempts, eleven
probes, 1.0 each. What it measured was not what "scored 1.0 on the exam" means to anybody reading
the row.

The collapse number learned this first (ADR-0070): 0.0 is a collapsed variance under v1 and a clean
sweep under v2, so an unlabelled number is not a weaker record, it is an unreadable one.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.operation_cert import OperationCertification
from src.services.operation.rubric import (
    SCORE_MEASURE_HELD_OUT_PASS_RATE_V1,
    SCORE_MEASURE_MERGED_DIMENSION_PASS_RATE_V2,
    SCORE_MEASURE_UNSTATED,
    merged_dimension_score,
)

pytestmark = pytest.mark.asyncio

FORGE = "cre-forge"
MODULE = "buyer_match"
AGENT = "cc49a49c-c7aa-459d-9ecb-ecb46100216f"
HASH = "648e494d60261641eef4ba4f5ce6f7e09103397c5eabffbfb29e5e8ea62ce502"

#: Verbatim from the voided `buyer_match` row: three FAIL, two PASS.
AS_ISSUED = [
    {"dimension": "sequence_correctness", "verdict": "FAIL", "score": 0.0},
    {"dimension": "failure_recognition", "verdict": "FAIL", "score": 0.0},
    {"dimension": "escalation_discipline", "verdict": "FAIL", "score": 0.0},
    {"dimension": "never_do_adherence", "verdict": "PASS", "score": 1.0},
    {"dimension": "protocol_conformance", "verdict": "PASS", "score": 1.0},
]


def _body(**over: object) -> dict:
    outcome: dict = {
        "agent_id": AGENT,
        "module_id": MODULE,
        "forge_id": FORGE,
        "functions_certified": 0,
        "functions_in_module": 5,
        "passed": True,
        "score": 1.0,
        "threshold": 1.0,
        "agent_model": "ollama/phi4:latest",
        "operation_rubric_results": AS_ISSUED,
        "per_scenario_class_results": [
            {"scenario_class": "happy_path", "verdict": "FAIL"},
            {"scenario_class": "never_do_violation", "verdict": "PASS"},
        ],
    }
    outcome.update(over)
    return {
        "instruction_set_ref": {
            "forge_id": FORGE,
            "module_id": MODULE,
            "instruction_version": "1.1.0",
            "forge_api_version": "1.4.0",
            "content_hash": HASH,
            "authored_by": "the-office",
        },
        "run_content_hash": HASH,
        "run_ref": "op-run-adr0093",
        "operation_rubric_version": "0.2.0",
        "agent_outcomes": [outcome],
    }


async def _row(client: AsyncClient, db: AsyncSession, body: dict) -> OperationCertification:
    res = await client.post("/api/operation/gate-result", json=body)
    assert res.status_code == 200, res.text
    row = (
        await db.execute(
            select(OperationCertification).where(OperationCertification.moduleId == MODULE)
        )
    ).scalars().first()
    assert row is not None
    return row


# =================================================================================================
# The measure
# =================================================================================================


def test_v2_cannot_read_one_point_zero_beside_a_failing_dimension() -> None:
    """The property the ruling asks for, stated directly. A FAIL is in the denominator."""
    score, measure = merged_dimension_score(AS_ISSUED)

    assert measure == SCORE_MEASURE_MERGED_DIMENSION_PASS_RATE_V2
    assert score == pytest.approx(2 / 5)
    assert score != 1.0


def test_a_clean_sweep_still_reads_one_point_zero() -> None:
    clean = [{"dimension": f"d{i}", "verdict": "PASS", "score": 1.0} for i in range(5)]

    assert merged_dimension_score(clean)[0] == 1.0


def test_dimensions_that_never_ran_are_in_neither_half_of_the_fraction() -> None:
    """A half that did not run must neither flatter the score nor sink it."""
    mixed = [
        {"dimension": "a", "verdict": "PASS", "score": 1.0},
        {"dimension": "b", "verdict": "FAIL", "score": 0.0},
        {"dimension": "c", "verdict": "NOT_RUN", "score": None},
        {"dimension": "d", "verdict": "not_applicable", "score": None},
    ]

    assert merged_dimension_score(mixed)[0] == pytest.approx(1 / 2)


def test_no_scored_dimension_has_no_rate_and_that_is_not_zero() -> None:
    """0.0 would be a claim about the agent rather than about the run — the same rule
    `AgentRunOutcome.score` already follows."""
    score, measure = merged_dimension_score([{"dimension": "a", "verdict": "NOT_RUN"}])

    assert score is None
    assert measure == SCORE_MEASURE_MERGED_DIMENSION_PASS_RATE_V2


def test_the_two_measures_are_distinct_names() -> None:
    assert SCORE_MEASURE_HELD_OUT_PASS_RATE_V1 != SCORE_MEASURE_MERGED_DIMENSION_PASS_RATE_V2
    assert "held_out" in SCORE_MEASURE_HELD_OUT_PASS_RATE_V1
    assert "merged" in SCORE_MEASURE_MERGED_DIMENSION_PASS_RATE_V2


# =================================================================================================
# The label reaches the row
# =================================================================================================


async def test_the_row_records_the_score_and_the_rule_that_produced_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    row = await _row(
        client,
        db_session,
        _body(score=0.4, score_measure=SCORE_MEASURE_MERGED_DIMENSION_PASS_RATE_V2),
    )

    assert row.score == pytest.approx(0.4)
    assert row.scoreMeasure == SCORE_MEASURE_MERGED_DIMENSION_PASS_RATE_V2
    assert row.state == "failed"  # ADR-0092, beside it


async def test_an_unlabelled_score_is_named_rather_than_refused_or_guessed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """**Not a 422 and not a guess.**

    ADR-0087 settled the shape: SimForge declares a field first, and refusing every payload that
    has not learned to fill it would stop a venture already certifying. Labelling it v1 would
    invent a fact about somebody else's measure, which is this defect pointing the other way.
    """
    row = await _row(client, db_session, _body(score=1.0))

    assert row.score == pytest.approx(1.0)
    assert row.scoreMeasure == SCORE_MEASURE_UNSTATED


async def test_a_row_with_no_score_carries_no_measure(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The CHECK forbids a number whose rule is unknown. It does not require a rule where there is
    no number: a department unit has no dimensions and a timed-out run got no answer."""
    row = await _row(client, db_session, _body(score=None, threshold=None, passed=False))

    assert row.score is None
    assert row.scoreMeasure is None
