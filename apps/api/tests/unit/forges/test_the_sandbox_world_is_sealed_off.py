"""ADR-0166: the sandbox world generator reads nothing held out.

It must not import, call or read the held-out probe generator, a partition, `neverDoGroups` or
any held-out scenario. The guarantee is structural: the generator and the page script reach no
SimForge module but the generator and the standard library, call nothing that reads a file, the
environment or a module chosen at run time, and name nothing held out.

The import walk is the one `test_the_handover_test_does_not_exist` uses, repeated so this file's
guarantee does not become a function of another file's helper.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

API = Path(__file__).resolve().parents[3]
SRC = API / "src"
GENERATOR = "src.services.forges.deal_desk_world"
SCRIPT = API / "scripts" / "sandbox_world_page.py"

#: Standard-library modules the generator may import, and nothing else.
GENERATOR_STDLIB = {
    "__future__",
    "dataclasses",
    "hashlib",
    "html",
    "json",
    "random",
    "typing",
    "uuid",
}
#: Names that would mean the generator touched what is held out.
FORBIDDEN_NAMES = ("held_out", "heldout", "neverdo", "never_do", "partition", "look_alike")
#: Calls that read a file, the environment, or a module chosen at run time.
FORBIDDEN_CALLS = {
    "open",
    "read_text",
    "read_bytes",
    "getenv",
    "__import__",
    "import_module",
    "exec",
    "eval",
    "load",
    "loads",
}


def _path(module: str) -> Path:
    path = SRC.joinpath(*module.split(".")[1:]).with_suffix(".py")
    return path if path.exists() else SRC.joinpath(*module.split(".")[1:], "__init__.py")


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imports(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    return names


def _reachable(entry: ast.AST) -> set[str]:
    """Every `src.*` module transitively imported from `entry`."""
    seen: set[str] = set()
    stack = [m for m in _imports(entry) if m.startswith("src.")]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        path = _path(name)
        if path.exists():
            stack.extend(m for m in _imports(_tree(path)) if m.startswith("src."))
    return seen


def test_the_generator_and_its_page_script_reach_no_other_simforge_module() -> None:
    for tree in (_tree(_path(GENERATOR)), _tree(SCRIPT)):
        assert _reachable(tree) <= {GENERATOR}


def test_the_generator_imports_only_the_standard_library_it_needs() -> None:
    imported = _imports(_tree(_path(GENERATOR)))
    assert imported <= GENERATOR_STDLIB, imported - GENERATOR_STDLIB
    assert all(m in sys.stdlib_module_names or m == "__future__" for m in imported)


def test_the_generator_reads_no_file_environment_or_module_by_name() -> None:
    for node in ast.walk(_tree(_path(GENERATOR))):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
            assert name not in FORBIDDEN_CALLS, name
        if isinstance(node, ast.Attribute):
            assert node.attr != "environ"


def test_the_generator_names_nothing_held_out() -> None:
    for path in (_path(GENERATOR), SCRIPT):
        text = path.read_text(encoding="utf-8").lower().replace("-", "_")
        for name in FORBIDDEN_NAMES:
            assert name not in text, (path.name, name)


def test_a_held_out_import_would_be_caught() -> None:
    """Not vacuous: a generator importing the held-out side fails the walk."""
    reached = _reachable(ast.parse("from src.services.operation.held_out import x\n"))
    assert "src.services.operation.held_out" in reached
    assert not reached <= {GENERATOR}
