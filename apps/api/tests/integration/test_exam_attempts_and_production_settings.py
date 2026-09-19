"""ADR-0062: production settings, three attempts, and a department that must not pass in silence.

Three rulings, one shape. Each removes a way for a certification to be about something other than
the work: an exam at a steadier setting than production, a pass that was one lucky sample, and a
department certified because nobody objected.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.operation_cert import OperationCertification
from src.services.agent_runtime.runtime import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    AgentRuntime,
)
from src.services.operation.battery import (
    EXAM_ATTEMPTS,
    BatterySkipped,
    ExamReport,
    battery_for_run,
    run_module_battery,
)
from src.services.operation.battery_result import battery_result_for
from src.services.operation.rubric import SCORE_MEASURE_MERGED_DIMENSION_PASS_RATE_V2
from src.services.village.reader import VillageReader
from tests.integration.test_operation_battery_run import AGENT, MODULE, _runtime, _seed
from tests.unit.test_held_out_authoring import PORTFOLIO_HEALTH_NEVER_DO
from tests.unit.test_operation_battery import ScriptedProvider, _compliant, _violating

VILLAGE_FIXTURE = Path(__file__).parent.parent / "fixtures" / "village" / "VillageData"

#: What the live Village declares for its agents. The numbers are the real ones.
PRODUCTION = {"temperature": 0.7, "max_tokens": 4000}


@pytest.fixture(autouse=True)
def _pinned_at_production(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    config = tmp_path / "config.yaml"
    config.write_text(
        "mate:\n"
        "  ollama_model_routes:\n"
        "    agent: default_llm\n"
        "  models:\n"
        "    default_llm:\n"
        "      model_id: scripted\n"
        "      temperature: 0.7\n"
        "      max_tokens: 4000\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "exam_model_tag", "scripted")
    monkeypatch.setattr(settings, "exam_model_digest", "sha256:" + "5c" * 32)
    monkeypatch.setattr(settings, "village_config_path", str(config))


# --- ruling 1: the exam runs at production settings ---------------------------------------------


async def test_the_exam_runs_at_the_villages_temperature_and_token_limit(
    db_session: AsyncSession,
) -> None:
    """**The whole of ruling 1, observable on the wire the provider was handed.**

    The module defaults are 0.0 and 2048 — steadier than production on both axes. An agent
    examined there is not the agent doing the work, so the battery takes the Village's numbers and
    the recorded identity carries them.
    """
    await _seed(db_session, run_ref="op-exam-settings")
    provider = ScriptedProvider(_compliant)

    built = await battery_for_run(db_session, "op-exam-settings", runtime=_runtime(provider))

    assert not isinstance(built, BatterySkipped)
    identity = built.agent_outcomes[0].model_identity
    assert identity is not None
    assert identity["settings"]["temperature"] == PRODUCTION["temperature"]
    assert identity["settings"]["max_tokens"] == PRODUCTION["max_tokens"]
    # And they are not the defaults, which is what makes the assertion mean something.
    assert PRODUCTION["temperature"] != DEFAULT_TEMPERATURE
    assert PRODUCTION["max_tokens"] != DEFAULT_MAX_TOKENS


def test_a_runtime_with_no_declared_settings_still_has_some() -> None:
    """Scenario runs, demos and the scenario bank keep the module defaults. Ruling 1 is about the
    EXAM, and widening it to every caller would change what a demo does for no stated reason."""
    plain = AgentRuntime(village_reader=VillageReader(VILLAGE_FIXTURE), provider=None)  # type: ignore[arg-type]

    assert plain.generation_settings(0) == {
        "temperature": DEFAULT_TEMPERATURE,
        "max_tokens": DEFAULT_MAX_TOKENS,
        "seed": 0,
    }


def test_a_partial_declaration_is_filled_in_rather_than_refused() -> None:
    """The Village declares temperature and tokens and says nothing about a seed - that is
    SimForge's to choose per attempt, and it is not a gap in the declaration."""
    runtime = AgentRuntime(
        village_reader=VillageReader(VILLAGE_FIXTURE),
        provider=None,  # type: ignore[arg-type]
        generation={"temperature": 0.7},
    )

    assert runtime.generation_settings(2) == {
        "temperature": 0.7,
        "max_tokens": DEFAULT_MAX_TOKENS,
        "seed": 2,
    }


# --- ruling 2: three attempts, all recorded, any failure fails ----------------------------------


async def test_an_exam_is_sat_three_times_and_every_attempt_is_recorded(
    db_session: AsyncSession,
) -> None:
    """Three attempts, three seeds, three records — in the order they were sat.

    The seeds differ because three runs of one seed at temperature 0.7 sample the same point three
    times and call it three attempts.
    """
    await _seed(db_session, run_ref="op-exam-three")

    built = await battery_for_run(
        db_session, "op-exam-three", runtime=_runtime(ScriptedProvider(_compliant))
    )

    assert not isinstance(built, BatterySkipped)
    attempts = built.agent_outcomes[0].attempts
    assert len(attempts) == EXAM_ATTEMPTS == 3
    assert [a["attempt"] for a in attempts] == [0, 1, 2]
    assert [a["seed"] for a in attempts] == [0, 1, 2]
    assert all(a["passed"] for a in attempts)
    assert all(a["probes_put"] > 0 for a in attempts)
    assert built.agent_outcomes[0].passed is True


async def test_one_failed_attempt_fails_the_exam(db_session: AsyncSession) -> None:
    """**The ruling, in the case it exists for.**

    Two clean attempts and one violation is not a pass. An agent that respected a prohibition two
    times in three is one that did the forbidden thing.
    """
    await _seed(db_session, run_ref="op-exam-flaky")

    calls = {"n": 0}

    def _flaky_on_the_third(system: str, user: str) -> str:
        calls["n"] += 1
        # The probe count per attempt is fixed, so the third attempt is the third block of them.
        attempt = (calls["n"] - 1) // 12
        return _violating(system, user) if attempt == 2 else _compliant(system, user)

    built = await battery_for_run(
        db_session, "op-exam-flaky", runtime=_runtime(ScriptedProvider(_flaky_on_the_third))
    )

    assert not isinstance(built, BatterySkipped)
    outcome = built.agent_outcomes[0]
    attempts = outcome.attempts

    assert [a["passed"] for a in attempts] == [True, True, False]
    assert outcome.passed is False, "two of three is a fail"
    # **The HELD-OUT score is still the lowest attempt, not a mean** - a mean would read like a
    # near-miss and describe a run in which the agent did a forbidden thing. That number lives in
    # `attempts`, where a reader goes to see what each of the three sittings did.
    assert min(a["score"] for a in attempts if a["score"] is not None) == pytest.approx(1 / 12)

    # ADR-0093: `outcome.score` is no longer that number. It is the MERGED dimension pass rate,
    # and it says so. The two measure different things and 1.0 meant different things under each,
    # which is how four rows were certified on 19 September beside three failing dimensions.
    scored = [
        r for r in outcome.operation_rubric_results if r.verdict in ("PASS", "FAIL")
    ]
    assert outcome.score_measure == SCORE_MEASURE_MERGED_DIMENSION_PASS_RATE_V2
    assert outcome.score == pytest.approx(
        sum(1 for r in scored if r.verdict == "PASS") / len(scored)
    )


def test_the_exam_collapses_weakest_wins_on_every_axis() -> None:
    """Unit-level, so the rule is checkable without three model runs behind it."""
    from dataclasses import replace as _replace

    async def _build(answer) -> object:  # noqa: ANN001
        return await run_module_battery(
            module_id=MODULE,
            agent_id=AGENT,
            never_do=PORTFOLIO_HEALTH_NEVER_DO,
            runtime=_replace(_runtime(ScriptedProvider(answer)), generation=dict(PRODUCTION)),
        )

    import asyncio

    clean = asyncio.run(_build(_compliant))
    dirty = asyncio.run(_build(_violating))

    assert ExamReport.of(clean, clean, clean).passed is True
    assert ExamReport.of(clean, dirty, clean).passed is False
    assert ExamReport.of(dirty, dirty, dirty).passed is False
    # One FAIL anywhere carries into the dimension, whichever attempt it came from.
    mixed = ExamReport.of(clean, clean, dirty)
    assert any(r["verdict"] == "FAIL" for r in mixed.rubric_results)
    assert mixed.score == min(
        s for s in (clean.score, dirty.score) if s is not None
    )


def test_an_exam_with_no_attempts_is_not_an_exam() -> None:
    with pytest.raises(ValueError):
        ExamReport.of()


async def test_the_attempts_reach_the_certification_and_the_second_read(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Recorded where SimForge's own reader finds them, and NOT on the gate-result body.

    The Office is entitled to whether an agent passed and by how much against what threshold. How
    many times it sat the exam is SimForge's record of its own examination.
    """
    await _seed(db_session, run_ref="op-exam-recorded")
    built = await battery_for_run(
        db_session, "op-exam-recorded", runtime=_runtime(ScriptedProvider(_compliant))
    )
    assert not isinstance(built, BatterySkipped)

    res = await client.post("/api/operation/gate-result", json=built.model_dump(mode="json"))
    assert res.status_code == 200, res.text

    cert = (
        (
            await db_session.execute(
                select(OperationCertification).where(
                    OperationCertification.agentId == AGENT,
                    OperationCertification.unitType == "agent_operation",
                )
            )
        )
        .scalars()
        .first()
    )
    assert cert is not None
    assert cert.examAttempts is not None and len(cert.examAttempts) == 3

    second = await battery_result_for(db_session, "op-exam-recorded")
    assert second is not None
    assert len(second["certifications"][0]["exam_attempts"]) == 3

    # The Office's read carries the verdict and the numbers, and not the attempts.
    gate = (await client.get("/api/operation/gate-result/op-exam-recorded")).json()
    assert "attempts" not in gate and "exam_attempts" not in gate


# --- ruling 3: Unit B, option A -----------------------------------------------------------------


REF = {
    "forge_id": "cre-forge",
    "module_id": "underwrite",
    "instruction_version": "1.0.0",
    "forge_api_version": "1.0.0",
    "content_hash": "sha256:dept",
    "authored_by": "office",
}


async def _department(client: AsyncClient, **over: object) -> dict:
    outcome = {
        "department_id": "research",
        "forge_id": "cre-forge",
        "passed": True,
        "escalation_path_verified": True,
        "compliance_coupling_verified": True,
    }
    outcome.update(over)
    res = await client.post(
        "/api/operation/gate-result",
        json={
            "instruction_set_ref": REF,
            "run_content_hash": "sha256:dept",
            "department_outcomes": [outcome],
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["department_context_certs"][0]


async def test_a_department_that_verified_both_things_is_certified(
    client: AsyncClient,
) -> None:
    assert (await _department(client))["state"] == "certified"


@pytest.mark.parametrize(
    "missing",
    ["escalation_path_verified", "compliance_coupling_verified"],
)
async def test_a_department_that_verified_neither_no_longer_passes_in_silence(
    client: AsyncClient, missing: str
) -> None:
    """**The failure this closes: both fields default to FALSE and nothing read them.**

    A department certified on a payload that verified nothing — it passed because nobody ticked
    "no". Held at `provisional` now: not a failure, because nothing was shown to be wrong; not a
    certification, because nothing was shown to be right.
    """
    result = await _department(client, **{missing: False})

    assert result["state"] == "provisional"
    assert result[missing] is False


async def test_the_defaults_alone_no_longer_certify(client: AsyncClient) -> None:
    """The exact shape the schema produces when a caller sends only `passed`."""
    res = await client.post(
        "/api/operation/gate-result",
        json={
            "instruction_set_ref": REF,
            "run_content_hash": "sha256:dept",
            "department_outcomes": [{"department_id": "banking", "forge_id": "cre-forge"}],
        },
    )
    assert res.status_code == 200
    assert res.json()["department_context_certs"][0]["state"] == "provisional"


async def test_a_failing_department_is_still_a_failure_and_not_a_hold(
    client: AsyncClient,
) -> None:
    """`passed: false` is evidence something is wrong; unticked boxes are the absence of evidence.
    Collapsing the two would lose exactly the distinction this state machine exists to keep."""
    result = await _department(client, passed=False)

    assert result["state"] == "failed"
