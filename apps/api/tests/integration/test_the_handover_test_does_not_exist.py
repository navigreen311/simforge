"""`/api/version` says the department hand-over test does not exist, because it does not.

Ivan ruled Unit B in two parts: **option A** makes the department flags count now, **option B**
builds the real hand-over test later. Option B has not been built. `battery.py` has no Unit B path
and nothing in this service constructs a `DepartmentRunOutcome` — the router consumes them, and
only an outside submitter can produce one.

The Office's readiness gate asks whether a department can be tested. **Publishing nothing reads as
"SimForge did not say"**, which is the silence ADR-0101 found running the other way: two versions
that existed, were not published, and made a Forge that was answering read for two days as one that
had none. `false` is the answer this service actually has.

And a hand-coded boolean is exactly the shape that goes stale silently, so the second test below
binds it to the fact rather than to somebody's memory.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from httpx import AsyncClient

from src.services.operation.rubric import DEPARTMENT_HANDOVER_TEST

SRC = Path(__file__).resolve().parents[2] / "src"


def _imported_src_modules(entry: str) -> set[str]:
    """Every `src.*` module transitively imported from `entry`, read out of the ASTs.

    The same walk `test_the_router_cannot_reach_the_battery` uses, repeated rather than imported so
    that this file's guarantee does not quietly become a function of another file's helper.
    """
    seen: set[str] = set()
    stack = [entry]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        path = SRC.joinpath(*name.split(".")[1:]).with_suffix(".py")
        if not path.exists():
            path = SRC.joinpath(*name.split(".")[1:], "__init__.py")
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src."):
                stack.append(node.module)
            elif isinstance(node, ast.Import):
                stack.extend(a.name for a in node.names if a.name.startswith("src."))
    return seen


def _constructs(module: str, name: str) -> bool:
    """Does this module CALL `name`, as opposed to importing or annotating it?

    A call, because that is what producing an outcome looks like. `department_outcomes: list[X]` in
    a request schema is a field that receives one from outside, and reading that as construction
    would report a hand-over test where there is a mailbox.
    """
    path = SRC.joinpath(*module.split(".")[1:]).with_suffix(".py")
    if not path.exists():
        return False
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == name:
                return True
            if isinstance(func, ast.Attribute) and func.attr == name:
                return True
    return False


@pytest.mark.asyncio
async def test_the_version_route_says_the_handover_test_does_not_exist(
    client: AsyncClient,
) -> None:
    """**`is False`, not falsy.** A missing key is falsy in Python and is precisely the answer this
    test exists to distinguish from — "did not say" against "no"."""
    body = (await client.get("/api/version")).json()

    assert "department_handover_test" in body["exam"]
    assert body["exam"]["department_handover_test"] is False


@pytest.mark.asyncio
async def test_it_sits_in_the_exam_block_beside_the_versions(client: AsyncClient) -> None:
    """The Office reads exam facts out of `exam` and drops keys it does not transcribe, so the key
    lands at `exam.department_handover_test` or it lands nowhere. A flat key would be this side
    guessing at the other side's nesting — the defect that cost two days when the guess ran the
    other way (ADR-0101)."""
    body = (await client.get("/api/version")).json()

    assert set(body["exam"]) == {
        "response_protocol_version",
        "operation_rubric_version",
        "department_handover_test",
    }
    assert "department_handover_test" not in body


def test_the_flag_is_bound_to_the_fact_not_to_somebody_s_memory() -> None:
    """**Build the hand-over test and this test goes red until the flag flips.**

    Nothing reachable from the battery constructs a `DepartmentRunOutcome`. That is what "the
    hand-over test does not exist" means mechanically, and it is the thing a declaration has to be
    tied to — otherwise `DEPARTMENT_HANDOVER_TEST = False` outlives its own truth, which is the
    failure mode of every hand-maintained capability flag.
    """
    reachable = _imported_src_modules("src.services.operation.battery")

    assert "src.services.operation.held_out" in reachable, (
        "positive control: the battery reaches the authoring module, so an empty walk cannot be "
        "what passes this test"
    )
    producers = [m for m in reachable if _constructs(m, "DepartmentRunOutcome")]
    assert producers == [], (
        f"{producers} constructs a DepartmentRunOutcome, so a department run can now be graded - "
        "set DEPARTMENT_HANDOVER_TEST = True"
    )
    assert DEPARTMENT_HANDOVER_TEST is False


def test_the_type_exists_and_is_consumed_so_the_walk_is_looking_at_something_real() -> None:
    """The second control. `DepartmentRunOutcome` is a real declared type that the gate-result
    handler already reads — option A's mailbox. The walk above finding no producer is a fact about
    the battery, not a typo in a class name."""
    from src.schemas.operation_payloads import DepartmentRunOutcome

    assert DepartmentRunOutcome is not None

    router = SRC / "routers" / "operation.py"
    assert "department_outcomes" in router.read_text(encoding="utf-8")
