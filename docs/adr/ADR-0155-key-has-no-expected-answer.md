# ADR-0155 — An ungradable key says so

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-10 · **Built.**

## The ruling

> The grader reports an ungradable key (no expected_answer) as
> "the_scenario_was_never_put". That misled The Office's diagnosis. Give
> it its own reason (e.g. key_has_no_expected_answer) wherever a key can't
> be graded, distinct from a scenario never put.

## What was wrong

`grade_submitted` graded a key with no expected answer NOT_RUN, with the
reason `the_scenario_was_never_put`. That reason names a runner fault. The
probe had been put and answered. The Office went looking for a probe
nobody had put.

It was also checked after `answer is None`. So an unanswered ungradable
key read "never put" even with the label fixed in one branch.

## The rule now

A key's omissions are the submitter's, and they are named before anything
about the run:

| Absent | Verdict | Reason |
|---|---|---|
| situation (ADR-0087) | NOT_RUN | `the_submission_carried_no_situation` |
| expected answer | NOT_RUN | `key_has_no_expected_answer` |
| both | NOT_RUN | both, in that order |
| neither, and no answer | NOT_RUN | `the_scenario_was_never_put` |

`the_scenario_was_never_put` now means one thing: a gradable, puttable
key whose probe was not put.

## Where it shows

Every path that reports a submitted key's reasons goes through
`grade_submitted`:

- `scenarioReasons` on the certification (ADR-0147);
- `reasons` on each stored answer (ADR-0153);
- the merged verdicts behind the rubric.

The held-out half and the partition are SimForge-authored and always have
a key, so they have no such case.

## Unchanged

- **Verdicts.** NOT_RUN before, NOT_RUN now. Only the reason moves.
- **A protocol violation still comes first.** An unreadable answer is a
  FAIL whatever the key (ADR-0063). Whether that should hold for a key
  nobody can grade is not decided here.
- **No version bump.** ADR-0149 bumps the rubric for a change to
  `grade_scenario` or `battery_for_run`. This touches neither, and no
  verdict changes. Rows written before this ADR keep the old reason;
  nothing rewrites them.

## Tests

- An answered ungradable key reads `key_has_no_expected_answer`.
- An unanswered one reads the same, never `the_scenario_was_never_put`.
- Both omissions are named together.
- Through `battery_for_run`: every attempt's `scenario_reasons` and every
  stored answer carry the new reason.

All four fail on the code before this change.
