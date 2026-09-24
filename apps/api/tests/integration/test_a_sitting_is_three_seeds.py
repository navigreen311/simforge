"""A sitting is three seeds; an operator may re-sit at a named seed (ADR-0121).

Measured: phi4 is deterministic at fixed settings, so a single sitting is one
sample and a re-sit at the same seed reproduces it byte for byte.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scripts import resit_partition as cli
from src.models.held_out_partition import (
    HeldOutPartition,
    HeldOutPartitionOutcome,
    HeldOutPartitionVerdict,
)
from src.services.agent_runtime.llm_client import LLMResponse
from tests.integration.scheduler_path import fresh_session, run_scheduled
from tests.integration.test_gate_9_5_verdict import AUTH, bridged  # noqa: F401 - fixture
from tests.integration.test_operation_battery_run import (
    _examiner_pinned,  # noqa: F401 - autouse: pins the examiner for every test here
    _runtime,
)
from tests.integration.test_partition_sweep import AGENT, VENTURE, _seed, _serve
from tests.unit.test_operation_battery import ScriptedProvider, _compliant, _violating

pytestmark = pytest.mark.asyncio


class _BySeed(ScriptedProvider):
    """Answers by seed - the way a deterministic model differs between seeds."""

    def __init__(self, bad_seeds: set[int]) -> None:
        super().__init__(_compliant)
        self.bad = bad_seeds
        self.seeds: list[int] = []

    async def complete(self, *, system, messages, **kwargs):  # noqa: ANN001, ANN003, ANN201
        seed = int(kwargs.get("seed", 0))
        self.seeds.append(seed)
        user = messages[-1]["content"]
        answer = _violating if seed in self.bad else _compliant
        return LLMResponse(content=answer(system, user), provider=self.name)


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


# --- a sitting is three seeds ------------------------------------------------------


async def test_a_scheduled_sitting_puts_three_seeds_and_keeps_the_weakest(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    provider = _BySeed({1})
    _serve(monkeypatch, provider)

    await run_scheduled("partition_sweep", db_session)

    rows = await _rows(db_session)
    finals = [(r.seed, r.verdict) for r in rows if r.verdict != "IN_PROGRESS"]
    assert finals == [(0, "PASS"), (1, "FAIL"), (2, "PASS")]
    assert set(provider.seeds) == {0, 1, 2}, "the seed reaches the model"
    assert len({r.sittingId for r in rows}) == 1


async def test_every_outcome_row_records_its_seed(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    _serve(monkeypatch, _BySeed(set()))
    await run_scheduled("partition_sweep", db_session)

    async with fresh_session(db_session) as s:
        outcomes = (await s.execute(select(HeldOutPartitionOutcome))).scalars().all()
        verdicts = {v.id: v for v in (await s.execute(select(HeldOutPartitionVerdict))).scalars()}
    assert outcomes
    for o in outcomes:
        assert o.seed is not None and o.seed == verdicts[o.verdictId].seed


async def test_a_sitting_that_failed_one_seed_is_settled_and_not_sat_again(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DUE reads the sitting's weakest seed, not the latest row."""
    await _seed(db_session)
    _serve(monkeypatch, _BySeed({0}))
    await run_scheduled("partition_sweep", db_session)
    before = len(await _rows(db_session))

    await run_scheduled("partition_sweep", db_session)

    assert len(await _rows(db_session)) == before


# --- the operator's re-sit ----------------------------------------------------------


async def _resit(db: AsyncSession, seed: int, provider) -> dict:  # noqa: ANN001
    async with fresh_session(db) as s, fresh_session(db) as lock:
        return await cli.resit(s, lock, _pid[0], seed, runtime=_runtime(provider))


_pid: list[str] = []


async def test_a_resit_appends_a_new_sitting_and_touches_nothing_written(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pid[:] = [await _seed(db_session)]
    _serve(monkeypatch, _BySeed(set()))
    await run_scheduled("partition_sweep", db_session)
    before = [(r.id, r.verdict, r.seed, r.sittingId) for r in await _rows(db_session)]

    provider = _BySeed({5})
    out = await _resit(db_session, 5, provider)

    after = await _rows(db_session)
    assert [(r.id, r.verdict, r.seed, r.sittingId) for r in after[: len(before)]] == before
    new = after[len(before) :]
    assert [(r.seed, r.verdict) for r in new] == [(5, "IN_PROGRESS"), (5, "FAIL")]
    assert len({r.sittingId for r in new}) == 1
    assert new[0].sittingId not in {b[3] for b in before}
    assert set(provider.seeds) == {5} and out["put"] == 1


async def test_gate_9_5_reads_the_weakest_sitting_not_the_latest(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A FAIL at seed 5, then a clean re-sit at seed 6: the venture still reads FAIL."""
    _pid[:] = [await _seed(db_session)]
    _serve(monkeypatch, _BySeed(set()))
    await run_scheduled("partition_sweep", db_session)
    await _resit(db_session, 5, _BySeed({5}))
    await _resit(db_session, 6, _BySeed(set()))

    res = await bridged.post("/office/gate_9_5_verdict", json={"venture_id": VENTURE}, headers=AUTH)

    assert res.json()["verdict"] == "FAIL"
    assert set(res.json()) == {"venture_id", "partition_exists", "verdict", "decided_at"}


async def test_a_resit_of_an_unsealed_partition_is_refused_and_writes_nothing(
    db_session: AsyncSession,
) -> None:
    pid = await _seed(db_session, status="authoring")
    async with fresh_session(db_session) as s, fresh_session(db_session) as lock:
        with pytest.raises(cli.ResitRefused, match="not sealed"):
            await cli.resit(s, lock, pid, 1, runtime=_runtime(_BySeed(set())))
    assert await _rows(db_session) == []
    async with fresh_session(db_session) as s:
        assert (await s.get(HeldOutPartition, pid)).status == "authoring"


async def test_the_resit_is_no_route() -> None:
    """ADR-0050: nothing under src/ imports the operator's script."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "src"
    hits = [
        p.relative_to(src).as_posix()
        for p in src.rglob("*.py")
        if "resit_partition" in p.read_text(encoding="utf-8")
    ]
    assert hits == []
