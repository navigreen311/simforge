"""The exam ref names the examiner's settings (The Office decisions entry 355).

Ivan Green, 26 November 2026: *"A changed setting must make a new exam; an unchanged one must
still carry over as today."*

Measured before it was written: The Office's run ref named the manual, the key, the sections, the
protocol and the rubric, and not the model. With the manuals unchanged a move from 8192 to 16384
minted the 8192 exam's ref, and `open_run` handed back its graded run. Live, on 26 November:
Burkham-Wickmont's sealed partition holds 36 sittings from 4 November recording no examiner at
all, and Greenstone's 18 record `num_ctx` 8192. Without these checks, both would still count.

Three places compare, and each is tested here:

1. `GET /api/health/examiner-settings` states the five facts and the ref segment.
2. The battery refuses a ref whose segment is not its examiner's, and puts nothing.
3. Gate 9.5 counts, and the grader settles, only sittings at the examiner's settings now.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.held_out_partition import HeldOutPartitionVerdict
from src.services.agent_runtime.examiner_settings import (
    ExaminerSettingsUnknown,
    ref_segment,
    same_settings,
    settings_digest,
    settings_now,
    settings_of,
    settings_of_run_ref,
)
from src.services.operation.battery import (
    RESPONSE_PROTOCOL_VERSION,
    SKIP_EXAMINER_SETTINGS_MISMATCH,
    BatterySkipped,
    battery_for_run,
)
from src.services.operation.partition_grading import SKIP_NOT_AT_STATED_SETTINGS
from src.services.operation.partition_verdict import venture_verdict
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION, PARTITION_PROTOCOL_VERSION
from src.utils.time import utcnow
from tests.integration.examiner_now import AT_EXAMINER, at_examiner
from tests.integration.scheduler_path import fresh_session, run_scheduled
from tests.integration.test_operation_battery_run import (
    _examiner_pinned,  # noqa: F401 - autouse: pins the examiner for every test here
    _runtime,
)
from tests.integration.test_operation_battery_run import _seed as _seed_run
from tests.integration.test_partition_sweep import AGENT, DIGEST, FORGE, VENTURE, _seed, _serve
from tests.unit.test_operation_battery import ScriptedProvider, _compliant

pytestmark = pytest.mark.asyncio

#: A sitting or an exam at today's live window, examined now at 16384.
AT_8192 = at_examiner(num_ctx=8192)
assert settings.exam_num_ctx == 16384


def _segment(record: dict) -> str:
    facts = settings_of(record)
    assert facts is not None
    return ref_segment(settings_digest(facts))


def _ref(segment: str | None) -> str:
    tail = f":m{segment}" if segment else ""
    return (
        "office:greenstone:capitalforge:portfolio_health@taylor:abc:kfeed:s0ff"
        f"{tail}:p{RESPONSE_PROTOCOL_VERSION}"
    )


# ------------------------------------------------------------------ what the five facts are


async def test_the_examiner_now_is_the_pin_the_declaration_and_the_window() -> None:
    now = settings_now(FORGE)
    assert now == {
        "model": "scripted",
        "file_digest": "sha256:" + "5c" * 32,
        "temperature": 0.37,
        "max_tokens": 1536,
        "num_ctx": 16384,
    }
    assert same_settings(AT_EXAMINER, now), "a sitting graded by it names exactly these"


async def test_an_8192_record_is_not_the_examiner_at_16384() -> None:
    assert not same_settings(AT_8192, settings_now(FORGE))
    assert _segment(AT_8192) != _segment(AT_EXAMINER)


async def test_an_unchanged_examiner_names_the_same_segment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """At 8192 now, an 8192 record IS the examiner: nothing moved, so nothing re-sits."""
    monkeypatch.setattr(settings, "exam_num_ctx", 8192)
    assert same_settings(AT_8192, settings_now(FORGE))
    assert ref_segment(settings_digest(settings_now(FORGE))) == _segment(AT_8192)


async def test_a_record_that_cannot_name_all_five_matches_nothing() -> None:
    before_the_window = at_examiner()
    before_the_window["settings"] = {"temperature": 0.37, "max_tokens": 1536}  # pre-B131
    assert settings_of(before_the_window) is None
    assert not same_settings(before_the_window, settings_now(FORGE))
    assert not same_settings(None, settings_now(FORGE)), "pre-ADR-0167: no record at all"


async def test_a_temperature_of_0_and_of_0_0_are_one_setting() -> None:
    a = settings_of(at_examiner(temperature=0))
    b = settings_of(at_examiner(temperature=0.0))
    assert a is not None and b is not None
    assert settings_digest(a) == settings_digest(b)


async def test_an_unpinned_examiner_states_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "exam_model_digest", "")
    with pytest.raises(ExaminerSettingsUnknown):
        settings_now(FORGE)


@pytest.mark.parametrize(
    ("ref", "named"),
    [
        ("office:g:f:m@a:h:kabc:s0ff:m0123456789ab:p6.0.0:r0.5.0", "0123456789ab"),
        ("office:g:f:m@a:h:m0123456789ab", "0123456789ab"),
        ("office:g:f:m@a:h:kabc:p6.0.0", None),
        ("office:g:f:module@abcdef12:h", None),
        ("op-run-battery-1", None),
    ],
)
async def test_the_ref_names_its_settings_or_nothing(ref: str, named: str | None) -> None:
    assert settings_of_run_ref(ref) == named


# ---------------------------------------------------------------------------------- the route


async def test_the_route_states_the_facts_and_the_segment(client: AsyncClient) -> None:
    body = (await client.get("/api/health/examiner-settings", params={"forge_id": FORGE})).json()
    now = settings_now(FORGE)
    assert body["readable"] is True
    assert body["examiner_settings"] == now
    assert body["digest"] == settings_digest(now)
    assert body["ref_segment"] == ref_segment(settings_digest(now)) == _segment(AT_EXAMINER)


async def test_the_route_says_why_when_it_cannot(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "exam_model_digest", "")
    res = await client.get("/api/health/examiner-settings", params={"forge_id": FORGE})
    body = res.json()
    assert res.status_code == 200
    assert body["readable"] is False
    assert body["ref_segment"] is None and body["examiner_settings"] is None
    assert "EXAM_MODEL_DIGEST" in body["reason"]


# -------------------------------------------------------------------------------- the battery


async def test_a_ref_minted_for_8192_is_not_graded_at_16384(db_session: AsyncSession) -> None:
    ref = _ref(_segment(AT_8192))
    await _seed_run(db_session, run_ref=ref)
    provider = ScriptedProvider(_compliant)

    result = await battery_for_run(db_session, ref, runtime=_runtime(provider))

    assert isinstance(result, BatterySkipped)
    assert result.reason == SKIP_EXAMINER_SETTINGS_MISMATCH
    assert provider.prompts == [], "a refused run must put no probe"


async def test_a_ref_minted_for_the_examiner_now_is_graded(db_session: AsyncSession) -> None:
    ref = _ref(_segment(AT_EXAMINER))
    await _seed_run(db_session, run_ref=ref)

    result = await battery_for_run(db_session, ref, runtime=_runtime(ScriptedProvider(_compliant)))

    assert not isinstance(result, BatterySkipped)


async def test_a_ref_without_the_segment_is_not_refused_on_that_ground(
    db_session: AsyncSession,
) -> None:
    """A ref The Office carried over because its certification stands at these settings."""
    ref = _ref(None)
    await _seed_run(db_session, run_ref=ref)

    result = await battery_for_run(db_session, ref, runtime=_runtime(ScriptedProvider(_compliant)))

    assert not isinstance(result, BatterySkipped)


# ------------------------------------------------------------------- Gate 9.5 and the grader


async def _sat(db: AsyncSession, pid: str, identity: dict | None, verdict: str = "PASS") -> None:
    at = utcnow() - timedelta(hours=2)
    for n, state in enumerate(("IN_PROGRESS", verdict)):
        db.add(
            HeldOutPartitionVerdict(
                partitionId=pid,
                ventureId=VENTURE,
                agentId=AGENT,
                agentModelIdentity=identity,
                verdict=state,
                partitionDigest=DIGEST,
                protocolVersion=PARTITION_PROTOCOL_VERSION,
                rubricVersion=OPERATION_RUBRIC_VERSION,
                decidedAt=at + timedelta(minutes=n),
            )
        )
    await db.commit()


async def _answer(db: AsyncSession) -> str | None:
    async with fresh_session(db) as s:
        return (await venture_verdict(s, VENTURE, FORGE))["verdict"]


async def test_gate_9_5_does_not_count_a_pass_sat_at_8192(db_session: AsyncSession) -> None:
    pid = await _seed(db_session)
    await _sat(db_session, pid, AT_8192)
    assert await _answer(db_session) == "NOT_RUN"


async def test_gate_9_5_does_not_count_a_pass_that_names_no_examiner(
    db_session: AsyncSession,
) -> None:
    """Burkham-Wickmont's 36 sittings of 4 November, live, look like this."""
    pid = await _seed(db_session)
    await _sat(db_session, pid, None)
    assert await _answer(db_session) == "NOT_RUN"


async def test_gate_9_5_counts_a_pass_sat_at_the_examiner_now(db_session: AsyncSession) -> None:
    pid = await _seed(db_session)
    await _sat(db_session, pid, AT_EXAMINER)
    assert await _answer(db_session) == "PASS"


async def test_gate_9_5_counts_an_8192_pass_while_the_examiner_is_at_8192(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unchanged settings carry over as today."""
    monkeypatch.setattr(settings, "exam_num_ctx", 8192)
    pid = await _seed(db_session)
    await _sat(db_session, pid, AT_8192)
    assert await _answer(db_session) == "PASS"


async def _rows(db: AsyncSession) -> list[HeldOutPartitionVerdict]:
    async with fresh_session(db) as s:
        return list(
            (
                await s.execute(
                    select(HeldOutPartitionVerdict)
                    .where(HeldOutPartitionVerdict.agentId == AGENT)
                    .order_by(HeldOutPartitionVerdict.decidedAt, HeldOutPartitionVerdict.id)
                )
            )
            .scalars()
            .all()
        )


@pytest.mark.parametrize("identity", [AT_8192, None], ids=["at_8192", "no_examiner"])
async def test_an_agent_settled_at_other_settings_is_sat_again(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, identity: dict | None
) -> None:
    pid = await _seed(db_session)
    await _sat(db_session, pid, identity)
    provider = ScriptedProvider(_compliant)
    _serve(monkeypatch, provider)

    await run_scheduled("partition_sweep", db_session)

    new = (await _rows(db_session))[2:]
    assert provider.prompts, "the agent was put the partition again"
    assert [r.verdict for r in new] == ["IN_PROGRESS", "PASS"] * 3
    assert all(same_settings(r.agentModelIdentity, settings_now(FORGE)) for r in new)
    assert await _answer(db_session) == "PASS"


async def test_an_agent_settled_at_the_examiner_now_is_not_sat_again(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = await _seed(db_session)
    await _sat(db_session, pid, AT_EXAMINER)
    provider = ScriptedProvider(_compliant)
    _serve(monkeypatch, provider)

    await run_scheduled("partition_sweep", db_session)

    assert provider.prompts == []
    assert len(await _rows(db_session)) == 2


async def test_the_grader_puts_nothing_at_settings_gate_9_5_would_not_count(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runtime at 8192 while SimForge states 16384: a sitting written now would never count,
    and the next pass would put it again."""
    from src.services.operation import partition_grading

    pid = await _seed(db_session)
    provider = ScriptedProvider(_compliant)
    runtime = _runtime(provider, {"temperature": 0.37, "max_tokens": 1536, "num_ctx": 8192})
    async with fresh_session(db_session) as s:
        outcome = await partition_grading.grade_partition(s, pid, runtime=runtime)

    assert outcome.skipped == SKIP_NOT_AT_STATED_SETTINGS
    assert provider.prompts == []
    assert await _rows(db_session) == []
