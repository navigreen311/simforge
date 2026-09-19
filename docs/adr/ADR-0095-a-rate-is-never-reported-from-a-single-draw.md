# ADR-0095 — A rate is never reported from a single draw

**Status:** accepted · **Decided by:** Ivan Green, 19 September 2026 · **Recorded.**
**Evidence:** [One draw is not a rate](../one-draw-is-not-a-rate-2026-09-19.md).

---

## The ruling

> **A rate is never reported from a single draw.** At production temperature one probe says nothing
> about a rate; measurements quoted in reports are replicated, as the exam itself already requires
> with three attempts.

## What prompted it

Three figures were reported on 19 September, one draw each. Measured at 40:

| reported from one draw | measured |
|---|---|
| `malformed_input`'s act was `DECLINE` at 4.0.0 — "a regression" | `DECLINE` 9/40; `REFUSE` was already 25/40 |
| `escalation_required` answered `PROCEED` at 4.0.0 | `PROCEED` 12/40; `REFUSE` 22/40 was the plurality |
| the naming sentence did not prevent a spurious record | it **halves** them, 19/40 → 8/40 |

Two were wrong. The third was backwards — reported as a concern about a change that in fact
improved the thing being worried about.

**None of them was a careless reading of the sample.** Each described its own draw correctly. The
error was the same each time: treating one draw at temperature 0.7 as a rate.

## Why it is a ruling and not a habit

**The exam already enforces this and the reports about the exam did not.** ADR-0062 rules three
attempts at production settings with distinct seeds, weakest-wins, for exactly this reason — a pass
means passed every time, because one sample is a sample. `ExamReport.of` merges them. `examAttempts`
stores all three so a reader can see that three sittings stood behind a verdict rather than one
lucky draw.

An investigation that reads the same model, at the same settings, and reports a number from one
call is applying a weaker standard to the evidence than the engine applies to the agents. The
verdicts are replicated; the arguments about the verdicts were not.

## What it requires

**Any rate, proportion or "it now does X" in a report is measured at two or more independent runs
and both are shown.** Not an average of forty presented as a single figure — the replicates
separately, so a reader can see whether they agree. The measurement that followed this ruling shows
both halves of every arm for that reason: `18+17` against `13+12` is an argument, and `35/40`
against `25/40` alone is an assertion.

**A single draw may still be quoted, and must be labelled as one.** A verbatim answer is often the
clearest way to show what a grader compared, and the three probes in the ADR-0094 report were right
to be quoted. What they were not entitled to do is carry a claim about frequency.

**An arm that changes two things measures neither.** 4.0.0 and 5.0.0 differed in the protocol
sentence *and* the probe, and only a third arm holding one of them fixed could say which moved the
act. It was the probe; the protocol edit did nothing. Two arms would have attributed it to both.

## Not built as code

There is nothing to enforce in the engine — the engine already replicates. This binds the reports,
and the place it binds is the calibration journal and the read-only documents, where it is now
recorded.
