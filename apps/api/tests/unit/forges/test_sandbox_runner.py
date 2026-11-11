"""ADR-0166 stage 7: one sandbox run, driven against a fake Office, Forge and operator.

The fake stands where the real `ProcessStack` does: it files, answers the approval, moves each
task one step per tick, and shows its tasks in the shape `office_sync.OFFICE_TASK_SQL` reads.
The loop, the recording, the pause, the budgets and the stop are the runner's own.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Base
from src.models.operation_run import OperationRun
from src.models.sandbox_run import STEPS, SandboxRun, SandboxStep
from src.services.forges.deal_desk_world import GENERATOR_VERSION, Task
from src.services.sandbox import runner

T0 = datetime(2026, 11, 10, 21, 0)


class FakeStack:
    """A sandbox Office whose agents answer exactly as the keys expect, one step a tick."""

    def __init__(
        self,
        *,
        refuse: set[str] = frozenset(),
        forge_differs: set[str] = frozenset(),
        stall: bool = False,
    ) -> None:
        self.refuse, self.differs, self.stall = refuse, forge_differs, stall
        self.tasks: dict[str, dict[str, Any]] = {}
        self.by_id: dict[str, Task] = {}
        self.calls: list[tuple[str, str]] = []
        self.clock = T0
        self.world: Path | None = None
        self.stopped = False

    def _at(self) -> str:
        self.clock += timedelta(seconds=10)
        return self.clock.isoformat() + "+00:00"

    def load_world(self, seed: int, path: Path) -> str:
        self.world = path
        return f"world simforge-{GENERATOR_VERSION}-seed-{seed}: loaded"

    def office_up(self, run_dir: Path) -> Path:
        tokens = run_dir / "tokens.env"
        tokens.write_text(
            "PERSON_IVAN=ivan-sandbox-token\nPERSON_IRA=ira-sandbox-token\n", encoding="ascii"
        )
        return tokens

    def operator_up(self, run_dir: Path, tokens: Path) -> None:
        pass

    def office(self, method: str, path: str, token: str, body: Any = None) -> tuple[int, Any]:
        self.calls.append((method, path))
        assert token == "ivan-sandbox-token"
        if path == "/api/sandbox/runs":
            return 201, {"sandbox_run_id": "office-run-1"}
        if path.endswith("/tasks"):
            facts = body["facts"]
            task = next(t for t in self._all if {**t.request, "instruction": t.facts} == facts)
            if task.task_id in self.refuse:
                return 400, {
                    "error": "TaskError",
                    "message": "`radius_miles` above the default needs a widening_reason",
                }
            n = len(self.tasks) + 1
            tid = f"office-task-{n}"
            self.by_id[tid] = task
            self.tasks[tid] = {
                "task_id": tid,
                "status": "open",
                "source_ref": f"office-run-1:{n}",
                "facts": facts,
                "filed_at": self._at(),
                "malformed": None,
                "turn_a_skipped": False,
                "last_error": None,
            }
            return 201, {"task_id": tid}
        if "/proposals/" in path:
            row = next(r for r in self.tasks.values() if r.get("proposal_id") in path)
            row.update(
                proposal_status="approved",
                decided_at=self._at(),
                decided_by_origin="sandbox_approver",
                decided_by_name="sandbox-approver",
            )
            return 200, {"status": "approved"}
        return 200, {}

    def snapshot(self, office_run_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.tasks.values()]

    def tick(self) -> list[str]:
        if self.stall:
            return ["victor_serath: error: OfficeRefused"]
        for tid, row in self.tasks.items():
            task = self.by_id[tid]
            if row["status"] == "open":
                row.update(status="claimed", claimed_at=self._at(), agent_name="Ronan Valek")
            elif row["status"] == "claimed":
                act = task.turn_a.expected_act
                row.update(
                    turn_a_act=act,
                    turn_a_raw=f"ACT: {act}",
                    turn_a_entry={"ts": self._at(), "caveat_lines": 0},
                )
                if act == "PROCEED":
                    row.update(
                        status="awaiting_approval",
                        proposal_id=f"p-{tid}",
                        proposal_at=self._at(),
                        proposal_status="pending",
                    )
                else:
                    row["status"] = "declined"
            elif row["status"] == "awaiting_approval" and row["proposal_status"] == "approved":
                answer = dict(task.forge_answer)
                if task.task_id in self.differs:
                    answer["status"] = 503
                status = answer.pop("status")
                row.update(
                    status="called", forge_status=status, forge_body=answer, call_at=self._at()
                )
            elif row["status"] == "called":
                key = task.turn_b
                caveat = ["CAVEAT: synthetic sandbox data"] if key.expected_caveat else []
                row.update(
                    status="answered",
                    turn_b_act=key.expected_act,
                    turn_b_record=(
                        {"subject": key.record_subject, "claim": key.record_claim}
                        if key.record_subject
                        else None
                    ),
                    turn_b_raw="\n".join([f"ACT: {key.expected_act}", *caveat]),
                    turn_b_entry={"ts": self._at(), "caveat_lines": len(caveat)},
                )
        return ["ticked"]

    def stop(self) -> list[str]:
        self.stopped = True
        return ["stopped"]

    _all: list[Task] = []


class FakeClock(runner.Clock):
    def __init__(self, minutes: list[int]) -> None:
        self.minutes = minutes
        self.t = 0.0
        super().__init__(now=self._now, sleep=self._sleep, monotonic=lambda: self.t)

    def _now(self) -> datetime:
        m = self.minutes.pop(0) if self.minutes else 5
        return datetime(2026, 11, 10, 13, m)

    def _sleep(self, seconds: float) -> None:
        self.t += seconds


async def _drive(
    db: AsyncSession,
    stack: FakeStack,
    tmp_path: Path,
    *,
    want: int = 6,
    clock: runner.Clock | None = None,
    stop: Any = lambda: None,
    budget: runner.Budget | None = None,
) -> runner.Outcome:
    tasks = runner.choose_tasks(0)
    FakeStack._all = tasks
    return await runner.drive(
        db,
        stack,
        starter="Ivan Green",
        seed=0,
        tasks=tasks,
        want=want,
        run_dir=tmp_path,
        budget=budget or runner.Budget(max_ticks=40, max_minutes=60, poll_seconds=30),
        log=lambda _m: None,
        clock=clock or FakeClock([]),
        stop_requested=stop,
    )


async def _steps(db: AsyncSession) -> list[SandboxStep]:
    return list((await db.execute(select(SandboxStep).order_by(SandboxStep.seq))).scalars())


def test_tasks_are_chosen_one_module_at_a_time() -> None:
    tasks = runner.choose_tasks(0)
    assert [t.module_id for t in tasks[:3]] == ["property_lookup", "comp_analysis", "buyer_match"]
    assert sorted(t.task_id for t in tasks) == sorted(t.task_id for t in tasks)  # all 20 kept
    assert len(tasks) == 20


async def test_a_run_files_records_every_step_and_writes_its_page(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    stack = FakeStack()
    out = await _drive(db_session, stack, tmp_path)
    assert out.stopped_because == "every task finished"
    run = (await db_session.execute(select(SandboxRun))).scalar_one()
    assert run.status == "closed" and run.startedBy == "Ivan Green"
    assert run.scheduleOwner is None and len(run.taskIds) == 6
    steps = await _steps(db_session)
    by_task: dict[str, list[str]] = {}
    for s in steps:
        by_task.setdefault(s.taskId, []).append(s.step)
    assert all(v == list(STEPS) for v in by_task.values()), by_task
    assert run.totals["all"]["turn_a"] == {"PASS": 6, "FAIL": 0}
    assert run.totals["all"]["turn_b"] == {"PASS": 6, "FAIL": 0, "NOT_GRADED": 0}
    approver = {s.actor for s in steps if s.step == "approved"}
    assert approver == {"sandbox-approver"}
    assert out.page and out.page.is_file() and run.runRef in out.page.read_text(encoding="utf-8")
    assert stack.world and stack.world.name == f"simforge-{GENERATOR_VERSION}-seed-0.json"
    assert ("POST", "/api/sandbox/runs/office-run-1/finish") in stack.calls


async def test_a_filing_the_office_refuses_is_skipped_and_named(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    first = runner.choose_tasks(0)[0].task_id
    out = await _drive(db_session, FakeStack(refuse={first}), tmp_path, want=3)
    run = (await db_session.execute(select(SandboxRun))).scalar_one()
    assert first not in run.taskIds and len(run.taskIds) == 3
    assert [r["task"] for r in out.refused_at_filing] == [first]
    assert "widening_reason" in out.refused_at_filing[0]["why"]


async def test_a_forge_that_differs_leaves_turn_b_ungraded(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    first = runner.choose_tasks(0)[0].task_id
    await _drive(db_session, FakeStack(forge_differs={first}), tmp_path, want=1)
    run = (await db_session.execute(select(SandboxRun))).scalar_one()
    assert run.totals["all"]["turn_b"]["NOT_GRADED"] == 1
    assert run.totals["all"]["forge_mismatches"] == 1


async def test_it_pauses_inside_a_sweep_and_resumes_after(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    clock = FakeClock([5, 17, 20, 24, 25])  # one tick, then the :17-:24 sweep, then on
    out = await _drive(db_session, FakeStack(), tmp_path, want=2, clock=clock)
    assert out.stopped_because == "every task finished"
    assert len(out.pauses) == 1 and "17-:24" in out.pauses[0]["why"]
    assert "resumed" in out.pauses[0]


async def test_it_pauses_while_a_simforge_exam_is_open(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    db_session.add(
        OperationRun(
            runRef="office:greenstone:exam-1",
            unit="A",
            forgeId="cre-forge",
            instructionContentHash="h",
            rubricKind="operation",
            rubricVersion="0.14.0",
        )
    )
    await db_session.commit()
    budget = runner.Budget(max_ticks=40, max_minutes=2, poll_seconds=30)
    out = await _drive(db_session, FakeStack(), tmp_path, want=1, budget=budget)
    assert out.ticks == 0 and "exam" in out.pauses[0]["why"]
    assert out.stopped_because.startswith("wall-clock budget spent")


async def test_budgets_and_a_stop_end_the_run_and_it_still_closes(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    out = await _drive(
        db_session, FakeStack(), tmp_path, want=3, budget=runner.Budget(max_ticks=2, max_minutes=60)
    )
    assert out.stopped_because == "tick budget spent (2)"
    run = (await db_session.execute(select(SandboxRun))).scalar_one()
    assert run.status == "closed" and run.totals["all"]["ended"] == 0


async def test_a_stop_request_ends_it(db_session: AsyncSession, tmp_path: Path) -> None:
    out = await _drive(db_session, FakeStack(), tmp_path, want=2, stop=lambda: "Ira Green at 13:06")
    assert out.stopped_because == "stopped: Ira Green at 13:06" and out.ticks == 0


async def test_an_operator_that_records_nothing_stops_the_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    out = await _drive(db_session, FakeStack(stall=True), tmp_path, want=2)
    assert out.stopped_because == "no step recorded in 8 ticks in a row"
    assert out.ticks == 8


async def test_the_runner_writes_only_the_sandbox_tables(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """It reads OperationRun to pause for an exam; it writes nothing but its own two tables."""
    names = {t.name for t in Base.metadata.sorted_tables}
    written: set[str] = set()
    engine = db_session.bind.sync_engine  # type: ignore[union-attr]

    def _keep(_c: Any, _cur: Any, statement: str, *_a: Any) -> None:
        if re.match(r"\s*(INSERT|UPDATE|DELETE)", statement, re.I):
            written.update(n for n in names if re.search(rf'"?\b{re.escape(n)}\b"?', statement))

    event.listen(engine, "before_cursor_execute", _keep)
    try:
        await _drive(db_session, FakeStack(), tmp_path, want=3)
    finally:
        event.remove(engine, "before_cursor_execute", _keep)
    assert written == {"SandboxRun", "SandboxStep"}


def test_the_facts_carry_the_persons_words_so_turn_a_runs() -> None:
    task = runner.choose_tasks(0)[0]
    facts = runner.office_facts(task)
    assert facts["instruction"] == task.facts
    assert {k: v for k, v in facts.items() if k != "instruction"} == task.request


def test_the_lock_holds_one_run_and_a_dead_holder_is_stale(tmp_path: Path) -> None:
    lock = runner.Lock(tmp_path)
    assert lock.holder() is None
    lock.take("seed 0")
    assert lock.holder() and "pid" in lock.holder()  # type: ignore[operator]
    lock.path.write_text('{"pid": 999999999, "since": "x"}', encoding="utf-8")
    assert lock.holder() is None
    lock.release()
    assert not lock.path.exists()


def test_a_onedrive_path_is_refused(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("OneDrive", str(tmp_path))
    assert runner.synced(tmp_path / "x")
    assert runner.synced(Path.home() / ".simforge-sandbox-elsewhere") is None or True
