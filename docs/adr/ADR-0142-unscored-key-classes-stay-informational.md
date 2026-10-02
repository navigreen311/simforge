# ADR-0142 — permission_denied and malformed_input stay informational

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-02 · **No code change.**

## The ruling

> permission_denied / malformed_input: leave them informational (record the
> ruling on ADR-0086's gap).

## The gap this closes

ADR-0086 found that `permission_denied` and `malformed_input` map only to
`protocol_conformance`. The Office's keys are excluded from that dimension
(`submitted_dimension_results`). These classes are graded and produce
verdicts, but they "move nothing about whether the agent certifies". No one
had ruled on that until now.

## What it means

- The class verdicts appear in `perScenarioClass` and nowhere else.
- They do not change the score, the verdict, the channel scores or the tier.
- A certified row can show these classes as FAIL. That is expected, not a
  defect.

On the r0.10.0 exams, `permission_denied` read FAIL on 14 of 15 exams,
including all six certified at 1.0. A replay reproduced the failures. The
agent chose ESCALATE or REFUSE where the key expects DECLINE.

## Revisit

Revisit this if either class is to gate. That would mean mapping the class to
a competence dimension, which would be a rubric version bump (ADR-0100).
