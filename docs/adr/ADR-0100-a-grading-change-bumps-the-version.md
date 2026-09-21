# ADR-0100 — A grading change bumps the rubric version

**Status:** accepted · **Decided by:** Ivan Green, 21 September 2026 · **Built.**
**Applies to:** [ADR-0099](ADR-0099-the-channel-survives-the-merge.md).

---

## The ruling

> **ADR-0099 changes how a verdict is computed, so it bumps the rubric version.** A grading change
> that does not bump the version lets an old verdict pass for a current one.

## Built

`OPERATION_RUBRIC_VERSION` **0.3.0 → 0.4.0**.

ADR-0099 moved three things that decide a verdict:

| | |
|---|---|
| `merge_dimension_results` | keys by `(dimension, channel)`, so both channels survive instead of one |
| `passed` | reads `restraint_failed(results)` alone, where it read every channel |
| `max_certified_trust_tier` | capped by `tier_for_channels`, where it was the flat ceiling |

None of those changes a payload's shape. All of them change what the same exam produces — which is
exactly the case the version exists for. A row stamped `0.3.0` would have meant two different rules
depending on the day it was written, and nothing on the row would say which.

## Why it is a ruling rather than a habit

**The version had already stopped tracking the thing it names.** ADR-0096 bumped 0.2.0 → 0.3.0 for
the channel split. ADR-0099 then changed the merge, the pass rule and the tier cap and left the
version alone, because it was framed as a repair rather than a change. From a reader's side there
is no such distinction: four certifications written on 21 September carry `0.3.0` and were computed
by a rule that no longer exists.

This is the same shape as ADR-0093's score measure — *an unlabelled number is not a weaker record,
it is an unreadable one* — and as ADR-0097's protocol major. A number that means different things
on different days is worse than no number, because it invites a comparison that cannot be made.

## The lineage, so a reader can place a row

```
0.2.0   everything before the split
0.3.0   ADR-0096: verdicts carry a channel
0.4.0   ADR-0099: the merge keeps both channels; `passed` reads restraint; the tier is capped
```

**The four certifications of 21 September stay at `0.3.0`**, which is true of them: they were
computed by that rule, and they are the rows ADR-0099 exists because of. Nothing is backfilled -
the same discipline ADR-0070 and ADR-0093 applied to their measures. A version is a statement about
how a row was produced, and it is never edited after the fact.

Suite: **1,172 pass, 2 skip.** `SCHEDULER_ENABLED` is off.
