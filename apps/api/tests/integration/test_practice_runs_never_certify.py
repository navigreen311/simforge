"""ADR-0157 ruling 1: practice runs never change certification, autonomy level, safe mode, or
promotion streaks. Only key-graded exams do.

The four hooks each have their test beside the hook's own tests, rewritten from "it fires" to "it
does not":

- `daily_regression`: `test_regression_sweep.py::test_a_practice_flip_does_not_suspend_the_cert`
  and `test_a_job_asserts_its_row.py::test_the_regression_wrapper_leaves_the_cert_active_...`
- safe mode: `test_safe_mode.py::test_a_practice_compliance_spike_does_not_raise_safe_mode` and
  `test_a_job_asserts_its_row.py::test_the_scheduled_trigger_writes_no_row_for_practice_failures`
- promotion: `test_autonomy_triggers.py::test_practice_streak_does_not_promote_l3_to_l4` and
  `::test_practice_streak_does_not_open_an_l5_approval`

`apply_run_triggers` had no test before this PR. Its tests are here, with the predicate's.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cert import AutonomyEvent
from src.models.run import Run
from src.models.scorecard import Scorecard
from src.services.cert.autonomy_triggers import apply_run_triggers
from src.services.practice import is_practice_run
from tests.integration.scheduler_path import fresh_session
from tests.integration.test_regression_sweep import _greenstone, _run_with_card, _seed_scenario


async def _scored_run(
    db_session: AsyncSession, client: AsyncClient, *, level: str, card: dict
) -> tuple[Run, Scorecard, str]:
    await client.post("/api/packs/", json={"pack_dir": _greenstone()})
    agent, scenario = await _seed_scenario(db_session)
    agent.currentAutonomyLevel = level
    run = await _run_with_card(db_session, agent, scenario, passed=False, minutes_ago=1)
    scorecard = (
        await db_session.execute(select(Scorecard).where(Scorecard.runId == run.id))
    ).scalar_one()
    for name, value in card.items():
        setattr(scorecard, name, value)
    await db_session.commit()
    return run, scorecard, agent.id


async def test_a_practice_compliance_failure_does_not_demote(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A P2 failure used to drop the agent to L2 inside the run's own request."""
    run, card, agent_id = await _scored_run(
        db_session, client, level="L5", card={"p2Compliance": False}
    )

    fired = await apply_run_triggers(db_session, run, card)

    assert fired == []
    async with fresh_session(db_session) as fresh:
        from src.models.agent import Agent

        agent = (await fresh.execute(select(Agent).where(Agent.id == agent_id))).scalar_one()
        assert agent.currentAutonomyLevel == "L5"
        events = (
            (await fresh.execute(select(AutonomyEvent).where(AutonomyEvent.agentId == agent_id)))
            .scalars()
            .all()
        )
        assert events == []


async def test_a_practice_cognitive_alert_does_not_demote(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """An ARC fragmentation alert used to drop the agent to L3."""
    run, card, agent_id = await _scored_run(
        db_session, client, level="L5", card={"c4ArcNarrativeCoherence": "fragmentation"}
    )

    fired = await apply_run_triggers(db_session, run, card)

    assert fired == []
    async with fresh_session(db_session) as fresh:
        from src.models.agent import Agent

        agent = (await fresh.execute(select(Agent).where(Agent.id == agent_id))).scalar_one()
        assert agent.currentAutonomyLevel == "L5"


async def test_every_run_is_a_practice_run(client: AsyncClient, db_session: AsyncSession) -> None:
    """No `Run` is graded against an answer key, so none is anything but practice. If a key-graded
    kind of `Run` is ever added, this test is the one that has to change, on purpose."""
    run, _, _ = await _scored_run(db_session, client, level="L1", card={})
    assert is_practice_run(run) is True
    for mode in ("sandbox", "integrated"):
        run.executionMode = mode
        assert is_practice_run(run) is True
