# ADR-0157 — Practice runs never certify

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-12 · **Ruling 1 built.**
Rulings 2 and 3 are recorded; nothing is voided by this ADR.

## Why

On 2026-10-12 a smoke test of one Greenstone scenario was stopped before
it ran. A trace showed that a practice run's scorecard feeds four hooks
that change certification state:

| hook | where | what a practice run did |
|---|---|---|
| `apply_run_triggers` | `routers/scenarios.py`, inside the run's own request | P2 fail: drop to L2. ARC alert: drop to L3 |
| `find_and_suspend_regressions` | `daily_regression`, 02:00 UTC | pass then fail: suspend the covering AgentCert and demote one level |
| `maybe_auto_activate` | `safe_mode_auto_trigger`, every 15 min | 5 P2 fails in an hour: global safe mode |
| `evaluate_promotion` | `POST /api/agents/{id}/autonomy/evaluate-promotion` | 3 clean runs plus a crisis pass: promote, or open an L5 approval |

The Office's verdict ingest was already isolated. It reads
`OperationRun` and `OperationCertification` only, and no operation code
reads `Run` or `Scorecard`.

## The rulings

> 1. Practice runs never change certification, autonomy level, safe
>    mode, or promotion streaks. Only key-graded exams do.
> 2. A certificate issued on stub-model or stub-judge output is not a
>    certification.
> 3. Never delete a run record to avoid a sweep.

## What changes (ruling 1)

**Every `Run` is a practice run.** The scenario runner writes it and the
rubric scores it: heuristics plus the LLM judge. `evaluation/service.py`
is the only caller of `get_judge_llm`. Nothing in `Run` or `Scorecard`
is graded against an answer key. Key-graded exams are `OperationRun`
and `OperationCertification`, graded by `held_out_scoring`,
`submitted_scoring` and `partition_grading`, with no judge.

`services/practice.py::is_practice_run` states that once. Each of the
four hooks consults it:

- `apply_run_triggers` returns `[]` before reading the agent.
- `_latest_two_runs` (regression sweep) drops practice runs **before**
  taking two. A `.limit(2)` first would hide a counting pair behind two
  practice runs.
- `maybe_auto_activate` drops practice rows before the threshold.
- `_clean_streak` and `_has_advanced_crisis_pass` skip practice runs.

**Consequence: all four hooks are now inert.** No key-graded evidence
reaches them. Feeding exam results into them is its own decision, not
built here. Until then:

- no run demotes an agent;
- `daily_regression` suspends nothing;
- safe mode is raised by hand only;
- no agent is promoted by streak.

Both run paths are covered: `/run` (which called `apply_run_triggers`)
and `/run-live` (which writes `Run` and `Scorecard` rows the three
sweeps read).

**Tests.** The eight tests that asserted a hook firing on `Run` rows
now assert that it does not, from a fresh session where they did
before. `apply_run_triggers` had no test; it has two now, in
`test_practice_runs_never_certify.py`, with a test pinning the
predicate.

## Not covered by this PR (ruling 1 reaches further)

These still accept practice runs, and ruling 1 forbids it. Each is
listed in `BACKLOG.md`:

- `issue_agent_cert` issues an AgentCert from a battery of `Run` ids.
- `reinstate_agent_cert` reinstates one from the same.
- `run_regression_sweep` (the nightly worker) re-runs scenarios to
  produce fresh evidence. It now produces practice runs that count for
  nothing.

## Ruling 2: recorded, not applied

Nothing is voided here. The read-only survey and a void proposal are in
the PR description. Two facts it depends on:

- **`stub-llm` on an AgentCert says nothing about the model.**
  `PinnedVersions.agent_model` defaults to `"stub-llm"`
  (`cert/snapshot.py:63`) and `issue_agent_cert` never sets it
  (`cert/registry.py:107`). Every AgentCert carries it, whatever ran.
- **The judge is unrecorded.** `Scorecard` has no provider column.

So ruling 2 cannot be applied by reading a label. Which certificates it
covers needs a ruling on what counts as proof.

## Ruling 3: recorded

No code deletes a `Run` to avoid a sweep. Option A of 2026-10-12 (run,
then delete the run before 02:00) is rejected. With ruling 1 built, the
reason for it is gone: a practice run no longer feeds the sweep.
