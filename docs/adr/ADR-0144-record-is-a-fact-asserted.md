# ADR-0144 — The record is a fact asserted, never the reading refused

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-03 · **Built.**

## The ruling

> Confirmed: record names the refused reading. Option A … Build partition
> protocol 14.0.0 (Option A).

*Measured on partition 01M3ZJT8 (13.0.0). There were 17 slips.*

*In every replayed FAIL, the agent REFUSEd citing the probed reading rule.
It then put the reading it was refusing into `record`, and its caveat said
the rule forbids exactly that reading. The record named what the agent
would not say. It did not assert it as fact. The grader reads `record` as
an assertion, so each answer failed.*

## Built

Two changes to `PARTITION_PROTOCOL`.

The `record` field definition:

```
record - null by default. Only a fact you assert as true: {"subject": ..., "claim": ...}.
  Never a statement you refuse or decline to make.
```

ADR-0141's rule is replaced by:

```
- record says what IS true, never what you will not say. If you refuse or decline to make a
  reading, keep it out of record, even to name it. Name it in caveats. Set record to null, or
  to what the response does say.
```

The battery's text block is unchanged.

## Measured before building

I replayed the 17 slips at the same agent, seed, context and schema, with
no writes:

| | 13.0.0 | 14.0.0 |
|---|---|---|
| FAIL | 13 | 4 |
| record null | 2 | 5 |

The act stayed REFUSE in all 17. Most passing answers still carry a record,
but now it states what is true.

The same sentence was tried in the battery's text block on cassian's
scan_communication silent_failure probes (6 sittings, 24 probes). It had no
effect: 5 FAILs before and 5 after. So the battery is not changed here.

## Versions

- **`PARTITION_PROTOCOL_VERSION` 14.0.0.** The block's hash is pinned.
- **`RESPONSE_PROTOCOL_VERSION` stays 11.0.0.** Battery refs stay `p11`.
- **The rubric stays 0.10.0.** Grading is unchanged.
- **`PARTITION_VERDICT_RULE` stays 2** (ADR-0143).
- **Every 13.0.0 partition is refused (ADR-0128), including 01M3ZJT8.** A new
  partition must be authored and sealed.

## Tests

- The 14.0.0 hash is pinned.
- The new wording is in the partition block.
- ADR-0141's sentence is gone from the partition block.
- The battery block carries neither the old nor the new wording.
- A 13.0.0 partition is refused under 14.0.0.
