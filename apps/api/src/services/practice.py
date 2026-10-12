"""Practice runs never change certification (ADR-0157, Ivan Green's ruling 1, 2026-10-12).

> Practice runs never change certification, autonomy level, safe mode, or promotion streaks.
> Only key-graded exams do.

**Every row in `Run` is a practice run.** The scenario runner writes it and the rubric scores it:
heuristic dimensions plus the LLM judge (`evaluation/service.py`, the only caller of
`get_judge_llm`). Nothing in `Run` or `Scorecard` is graded against an answer key. Key-graded exams
are a different record: `OperationRun` and `OperationCertification`, graded by
`held_out_scoring`, `submitted_scoring` and `partition_grading`.

So this predicate has no input that can make it false. That is the finding, not a placeholder: a
`Run` row carries nothing that could mark it key-graded. It is one function, not four inline
`if`s, so the four hooks that read `Run` share one statement of the rule:

- `autonomy_triggers.apply_run_triggers`: demotion after a scored run
- `regression_sweep.find_and_suspend_regressions`: the `daily_regression` job
- `safe_mode_service.maybe_auto_activate`: the `safe_mode_auto_trigger` job
- `autonomy_triggers.evaluate_promotion`: the clean streak and the advanced-crisis pass

With every `Run` excluded, all four are inert. Feeding key-graded exam results into them is a
separate decision, and it is not built.
"""

from __future__ import annotations

from src.models.run import Run

RULING = "ADR-0157 ruling 1: practice runs never change certification"


def is_practice_run(run: Run) -> bool:
    """True for every `Run`: no `Run` is graded against an answer key (see module docstring)."""
    return True
