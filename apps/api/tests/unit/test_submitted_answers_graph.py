"""ADR-0153 - the no-read-path check covers the submitted-answer store.

The reader is on The Office's request path; it must reach nothing that holds a held-out probe.
The writer must be reachable from the submitted half only, so a held-out answer has no way in.
"""

from __future__ import annotations

#: Modules that hold a held-out probe, its grading key, or the code that puts or grades one.
HELD_OUT_HOLDERS = {
    "src.services.operation.held_out",
    "src.services.operation.held_out_scoring",
    "src.services.operation.held_out_partition",
    "src.services.operation.partition_grading",
    "src.services.operation.battery",
    "src.services.operation.submitted_scoring",
    "src.workers.partition_sweep",
    "src.workers.battery_sweep",
}
READER = "src.services.operation.submitted_answers"


def test_the_reader_reaches_nothing_that_holds_a_held_out_probe() -> None:
    from tests.integration.test_gate_9_5_verdict import _reachable

    reachable = set(_reachable([READER]))
    assert READER in reachable  # positive control: the walk found the module
    assert "src.models.submitted_answer" in reachable
    assert not reachable & HELD_OUT_HOLDERS, sorted(reachable & HELD_OUT_HOLDERS)


def test_the_office_router_reaches_the_reader_and_still_no_partition_content() -> None:
    from tests.integration.test_gate_9_5_verdict import FORBIDDEN_MODULES, _reachable

    reachable = set(_reachable(["src.routers.office"]))
    assert READER in reachable
    assert not reachable & FORBIDDEN_MODULES
    assert "src.services.operation.held_out_scoring" not in reachable
    assert "src.services.operation.battery" not in reachable


def _calls_and_names() -> dict[str, tuple[set[str], set[str]]]:
    """Per src module: the functions that call `record_submitted_answer`, and whether it names
    `SubmittedProbeAnswer`."""
    import ast

    from tests.integration.test_gate_9_5_verdict import SRC

    out: dict[str, tuple[set[str], set[str]]] = {}
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        callers: set[str] = set()
        names: set[str] = set()
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for node in ast.walk(fn):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "record_submitted_answer"
                ):
                    callers.add(fn.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "SubmittedProbeAnswer":
                names.add("SubmittedProbeAnswer")
        if callers or names:
            rel = path.relative_to(SRC.parent).with_suffix("").as_posix().replace("/", ".")
            out[rel] = (callers, names)
    return out


def test_the_only_writer_is_the_submitted_half() -> None:
    """Held-out answers are never stored because nothing on the held-out path can store one."""
    found = _calls_and_names()
    callers = {m: c for m, (c, _) in found.items() if c}
    assert callers == {"src.services.operation.battery": {"run_submitted_battery"}}
    namers = {m for m, (_, n) in found.items() if n}
    # The model file DEFINES the class (a ClassDef, not a Name); the reader is the only user.
    assert namers == {READER}
