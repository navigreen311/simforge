"""A change to the grader bumps the rubric version (ADR-0149).

ADR-0147 changed how an exam's attempts become a verdict and left the rubric at
0.11.0, so two rows reading `0.11.0` could have been decided by two rules. The
rule: a change to `grade_scenario` or `battery_for_run` bumps the rubric; a
change confined to one key's content does not (`scenario_set_hash` names it).

Pinned on the functions' syntax trees with docstrings removed, so a comment or
docstring edit does not trip it and any change to what they do does.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import textwrap

from src.services.operation.battery import battery_for_run
from src.services.operation.held_out_scoring import grade_scenario
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION

GRADERS = (grade_scenario, battery_for_run)

#: sha256 over both functions' docstring-free syntax trees.
PINNED = {
    "0.12.0": "64fd40cfa63ea443e45903fb4e5b4860746649103e1048ef745676ff37e80fea",
    # ADR-0150 changed the parser, not these two functions.
    "0.13.0": "64fd40cfa63ea443e45903fb4e5b4860746649103e1048ef745676ff37e80fea",
}


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    node.body = body[1:] or [ast.Pass()]
    return tree


def grader_digest() -> str:
    h = hashlib.sha256()
    for fn in GRADERS:
        tree = _strip_docstrings(ast.parse(textwrap.dedent(inspect.getsource(fn))))
        h.update(ast.dump(tree, annotate_fields=True, include_attributes=False).encode())
    return h.hexdigest()


def test_the_grader_is_pinned_to_its_rubric() -> None:
    assert OPERATION_RUBRIC_VERSION in PINNED, "a new rubric version needs its grader pinned here"
    assert grader_digest() == PINNED[OPERATION_RUBRIC_VERSION], (
        "grade_scenario or battery_for_run changed without a rubric bump (ADR-0149). "
        "Bump OPERATION_RUBRIC_VERSION and pin the new digest."
    )


def test_a_comment_or_docstring_does_not_move_the_digest() -> None:
    src = 'def f(x):\n    """Doc."""\n    # a comment\n    return x\n'
    bare = "def f(x):\n    return x\n"
    one = ast.dump(_strip_docstrings(ast.parse(src)))
    two = ast.dump(_strip_docstrings(ast.parse(bare)))
    assert one == two
