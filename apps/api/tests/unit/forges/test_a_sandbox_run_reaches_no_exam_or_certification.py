"""ADR-0166 stage 5: a sandbox run reaches no exam, certification, tier or partition.

Two halves, as the ADR asks:

1. **Counted.** A sandbox run of several tasks, with turns that pass, fail and go ungraded, is
   recorded on a database that already holds an exam, a certification with a tier and a
   partition. Every table's row count is taken before and after, and every row of every table
   but the two sandbox tables is read back unchanged. While the run is recorded, no statement
   names any other table, read or write.
2. **Structural.** The import walk from the sandbox record reaches no model but its own and the
   approved-key model `submitted_scoring` imports for its types, no router and no exam, gate or
   certification service.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import event, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Base
from src.models.held_out_partition import HeldOutPartition
from src.models.operation_cert import OperationCertification
from src.models.operation_run import OperationRun
from src.services.forges.deal_desk_world import generate_tasks, generate_world
from src.services.sandbox import record

SRC = Path(__file__).resolve().parents[3] / "src"
ENTRY = "src.services.sandbox.record"
#: The sandbox package: the record, the results page and the demo's fake run (stage 6).
SANDBOX_MODULES = (
    ENTRY,
    "src.services.sandbox",
    "src.services.sandbox.page",
    "src.services.sandbox.demo",
)
SANDBOX_TABLES = {"SandboxRun", "SandboxStep"}
#: Everything the sandbox record may reach, and why.
ALLOWED = {
    ENTRY,
    "src.models.base",
    "src.models.sandbox_run",
    "src.services.forges.deal_desk_world",
    "src.utils.time",
    # The grader, unchanged. Its own imports: the rubric's constants, the held-out half's
    # reasons and `ProtocolViolation`, and the approved-key model it types `SubmittedKey` from.
    # The record calls `grade_submitted` only, which reads no table.
    "src.services.operation.submitted_scoring",
    "src.services.operation.held_out_scoring",
    "src.services.operation.held_out",
    "src.services.operation.rubric",
    "src.services.operation.state_machine",
    "src.services.operation.trust_tier",
    "src.models.operation_scenario",
}
#: What the record calls from the grader, and nothing else of it.
GRADER_NAMES = {"SubmittedKey", "grade_submitted", "ProtocolViolation"}
T0 = datetime(2026, 11, 9, 15, 0, 0)


def _path(module: str) -> Path:
    path = SRC.joinpath(*module.split(".")[1:]).with_suffix(".py")
    return path if path.exists() else SRC.joinpath(*module.split(".")[1:], "__init__.py")


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    return {n for n in names if n.startswith("src.")}


def _reachable(entry: str) -> set[str]:
    seen: set[str] = set()
    stack = [entry]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        if _path(name).exists():
            stack.extend(_imports(_path(name)))
    return seen


def test_the_sandbox_record_reaches_nothing_but_the_grader_and_its_own_tables() -> None:
    reached = _reachable(ENTRY)
    assert reached <= ALLOWED, sorted(reached - ALLOWED)
    for forbidden in (
        "src.models.operation_run",
        "src.models.operation_cert",
        "src.models.held_out_partition",
        "src.models.cert",
        "src.models.safe_mode",
        "src.models.run",
        "src.services.operation.battery",
    ):
        assert forbidden not in reached


def test_the_page_and_the_demo_reach_nothing_more_than_the_record() -> None:
    """Stage 6: the results page and the demo's fake run add only each other and the record."""
    for entry in SANDBOX_MODULES[2:]:
        reached = _reachable(entry)
        assert reached <= ALLOWED | set(SANDBOX_MODULES), sorted(reached - ALLOWED)


def test_the_record_uses_only_grade_submitted_from_the_grader() -> None:
    tree = ast.parse(_path(ENTRY).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "src.services.operation."
        ):
            assert {a.name for a in node.names} <= GRADER_NAMES, node.module


def test_a_walk_reaching_an_exam_would_be_caught() -> None:
    """Not vacuous: the walk sees what `battery` reaches."""
    reached = _reachable("src.services.operation.battery")
    assert "src.models.operation_run" in reached
    assert not reached <= ALLOWED


# --- counted ---------------------------------------------------------------------------------


async def _seed_exam_side(db: AsyncSession) -> None:
    db.add(
        OperationRun(
            runRef="office:greenstone:exam-1",
            unit="A",
            forgeId="cre-forge",
            instructionContentHash="h",
            rubricKind="operation",
            rubricVersion="0.14.0",
        )
    )
    db.add(
        OperationCertification(
            unitType="agent_operation",
            state="certified",
            forgeId="cre-forge",
            instructionVersion="1.0.0",
            forgeApiVersion="1.0.0",
            instructionContentHash="h",
            operationRubricVersion="0.14.0",
            maxCertifiedTrustTier="propose",
        )
    )
    db.add(HeldOutPartition(ventureId="greenstone", forgeId="cre-forge", authoredBy="Ivan Green"))
    await db.commit()


async def _counts(db: AsyncSession) -> dict[str, int]:
    out = {}
    for table in Base.metadata.sorted_tables:
        out[table.name] = (await db.execute(select(func.count()).select_from(table))).scalar_one()
    return out


async def _contents(db: AsyncSession) -> dict[str, list[tuple[Any, ...]]]:
    out = {}
    for table in Base.metadata.sorted_tables:
        if table.name in SANDBOX_TABLES:
            continue
        rows = (await db.execute(select(table))).all()
        out[table.name] = sorted((tuple(r) for r in rows), key=repr)
    return out


@contextmanager
def _tables_named(db: AsyncSession) -> Iterator[set[str]]:
    """Every table any statement names while the block runs."""
    names = {t.name for t in Base.metadata.sorted_tables}
    seen: set[str] = set()
    engine = db.bind.sync_engine  # type: ignore[union-attr]

    def _listen(_conn: Any, _cursor: Any, statement: str, *_a: Any) -> None:
        seen.update(n for n in names if re.search(rf'"?\b{re.escape(n)}\b"?', statement))

    event.listen(engine, "before_cursor_execute", _listen)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", _listen)


async def _a_run(db: AsyncSession) -> record.SandboxRun:
    """Five tasks: right answers, a wrong count, a Turn A DECLINE and a Forge that differs."""
    chosen = generate_tasks(generate_world(0))[:5]
    run = await record.open_run(
        db,
        venture="greenstone",
        seed=0,
        started_by="Ivan Green",
        task_ids=[t.task_id for t in chosen],
    )
    for n, t in enumerate(chosen):

        async def step(
            name: str, actor: str, payload: dict[str, Any] | None = None, t: Any = t, n: int = n
        ) -> None:
            await record.record_step(
                db,
                run,
                task_id=t.task_id,
                step=name,
                at=T0,
                actor=actor,
                payload=payload,
                sandbox_ids={"office_task": f"task-{n}"},
                agent_id="ava" if name == "claimed" else None,
            )

        await step("filed", "Ivan Green", {"facts": t.facts, "request": t.request})
        await step("claimed", "ava")
        if n == 3:
            await step("turn_a", "ava", {"act": "DECLINE"})
            continue
        await step("turn_a", "ava", {"act": "PROCEED"})
        await step("proposed", "ava", {"request": t.request})
        await step("approved", record.SANDBOX_APPROVER)
        answer = dict(t.forge_answer)
        if n == 4:
            answer["status"] = 500
        await step("forge_answer", "cre-forge-sandbox", answer)
        claim = (t.turn_b.record_claim or "") + ("9" if n == 2 else "")
        subject = t.turn_b.record_subject
        await step(
            "turn_b",
            "ava",
            {
                "act": t.turn_b.expected_act,
                "record": {"subject": subject, "claim": claim} if subject else None,
                "caveats": ["as returned"],
            },
        )
    return await record.close_run(db, run)


async def test_a_sandbox_run_changes_no_table_but_its_own(db_session: AsyncSession) -> None:
    await _seed_exam_side(db_session)
    before, contents = await _counts(db_session), await _contents(db_session)
    assert before["OperationRun"] == before["OperationCertification"] == 1
    assert before["HeldOutPartition"] == 1

    with _tables_named(db_session) as named:
        run = await _a_run(db_session)

    after = await _counts(db_session)
    assert after["SandboxRun"] == before["SandboxRun"] + 1
    assert after["SandboxStep"] == before["SandboxStep"] + 3 + 4 * 7
    assert {k: v for k, v in after.items() if k not in SANDBOX_TABLES} == {
        k: v for k, v in before.items() if k not in SANDBOX_TABLES
    }
    assert await _contents(db_session) == contents
    assert named == SANDBOX_TABLES, sorted(named ^ SANDBOX_TABLES)

    # The run itself: what was graded, and how.
    assert run.status == "closed"
    totals = run.totals["all"]
    assert totals["tasks"] == totals["ended"] == 5
    assert totals["turn_a"] == {"PASS": 4, "FAIL": 1}
    assert totals["turn_b"] == {"PASS": 2, "FAIL": 1, "NOT_GRADED": 1}
    assert totals["forge_mismatches"] == 1
    assert set(run.totals["agent"]) == {"ava"}


async def test_the_counts_would_see_a_write_to_an_exam_table(db_session: AsyncSession) -> None:
    """Not vacuous: a write to OperationRun moves the count and is named."""
    before = await _counts(db_session)
    with _tables_named(db_session) as named:
        await _seed_exam_side(db_session)
    assert (await _counts(db_session))["OperationRun"] == before["OperationRun"] + 1
    assert "OperationRun" in named


def test_nothing_reads_a_sandbox_table_but_the_record() -> None:
    """No module outside the sandbox package and its model names the sandbox tables."""
    own = {_path(m) for m in (*SANDBOX_MODULES, "src.models.sandbox_run", "src.models")}
    for path in SRC.rglob("*.py"):
        if path in own:
            continue
        body = path.read_text(encoding="utf-8")
        for name in ("SandboxRun", "SandboxStep", "services.sandbox"):
            assert name not in body, (path.relative_to(SRC), name)


async def test_the_sqlite_tables_carry_the_migrations_checks(db_session: AsyncSession) -> None:
    sql = "SELECT sql FROM sqlite_master WHERE name LIKE 'Sandbox%'"
    rows = (await db_session.execute(text(sql))).all()
    ddl = " ".join(r[0] or "" for r in rows)
    assert "sandbox_step_step" in ddl and "sandbox_run_status" in ddl


async def test_rendering_a_runs_page_only_selects_from_the_sandbox_tables(
    db_session: AsyncSession,
) -> None:
    """Stage 6: loading and rendering the page reads the two sandbox tables, writes nothing."""
    from src.services.sandbox.page import load_run, render_run_page

    await _seed_exam_side(db_session)
    run = await _a_run(db_session)
    before, contents = await _counts(db_session), await _contents(db_session)
    statements: list[str] = []
    engine = db_session.bind.sync_engine  # type: ignore[union-attr]

    def _keep(_conn: Any, _cursor: Any, statement: str, *_a: Any) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _keep)
    try:
        with _tables_named(db_session) as named:
            loaded, steps = await load_run(db_session, run.runRef)
            render_run_page(loaded, steps)
    finally:
        event.remove(engine, "before_cursor_execute", _keep)
    assert named == SANDBOX_TABLES
    assert statements and all(s.lstrip().upper().startswith("SELECT") for s in statements)
    assert await _counts(db_session) == before
    assert await _contents(db_session) == contents
