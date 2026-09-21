# ADR-0103 — A probe change is a protocol change, and the RECORD: NONE conflict is parked

**Status:** accepted · **Decided by:** Ivan Green, 21 September 2026 · **Recorded, not built.**

---

## The rulings

> **1. Any change to the rendered probe is a protocol change and bumps
> `RESPONSE_PROTOCOL_VERSION`.** The scenario-set hash covers the situation, not the probe, so
> without this two exams asking different questions hash identically.
>
> **2. The RECORD: NONE finding is parked, not dropped.** The protocol invites a record the key
> grades as a fault; it affects disposition only; fixing it — an ordered test for the record line,
> plus keys naming a subject and a claim — voids the 21 September exams and belongs with the
> disposition work for `auto_execute`.

---

## 1 · A probe change is a protocol change

### The gap

`scenario_set_hash` (ADR-0092 ruling 4) hashes nine fields per key. One of them is `situation`.
**None of them is the probe.**

The probe is not the situation. It is:

```
<situation, verbatim>  <naming sentence>  <claim sentence>
```

The situation is the submitter's and the hash covers it. The two sentences are **SimForge's**, and
nothing covers them. Reword them and every exam before and after carries the same
`scenarioSetHash` — a digest whose whole purpose is to say *these two exams were set the same
questions*, saying it falsely.

This was found while costing the fixes for the RECORD: NONE conflict, all of which change those
sentences. The ruling closes it before a fix lands rather than after.

### What is now versioned

Everything the agent reads, on either half of the battery:

| | |
|---|---|
| `_NAMING_SENTENCE`, `_OPTIONS_SENTENCE`, `_OPEN_CLAIM_SENTENCE` | `held_out.py` |
| the `"the request"` fallback subject | `submitted_scoring.probe_for` |
| the decline and over-read probe templates | `held_out.py` |
| `battery_system_context`, `RESPONSE_PROTOCOL`, the worked examples | `battery.py` |

`RESPONSE_PROTOCOL_VERSION` already moved for the last of these — 4.0.0 for the grammar, 5.0.0 for
ADR-0094's naming sentences, 6.0.0 for ADR-0097's ordered test. **The ruling is that the first four
rows are the same kind of change as the last**, and the version says so whichever one moves.

### Why the version and not a second hash

A second digest over the rendered probe would be exact, and it would also be a number nobody reads.
`RESPONSE_PROTOCOL_VERSION` is already published on `/api/version` (ADR-0101), already carried in
`mint_run_ref`, and already the thing The Office reads to decide whether a run is comparable. One
field that is read beats a truer field that is not.

### What it costs

Each bump voids cross-version comparison. ADR-0098 already rules that a measurement is compared
only against an arm measured beside it; this makes the version **state** the incomparability rather
than leave it to be remembered.

### Not enforced by a test today

No build was asked, and none was made. What enforcement would take, named so it is not re-derived:
a golden of the rendered probe text for a fixed key and a fixed obligation, stored beside the
protocol version, so an edit to any of the four rows above fails the suite until the version moves.
That is the same shape as the existing ADR-0050 import-graph walk — a test that fails on a change
rather than on a bug.

---

## 2 · The RECORD: NONE conflict — parked

Full finding: `docs/the-record-none-conflict-2026-09-21.md`. In short:

Six of the 31 keys across the three examined modules expect `RECORD: NONE`, and all six carry
`record_subject = None`, so the probe hands the agent the invented subject `` `the request` ``.
**62% of answers then record under it** (75 of 120, two replicates of ten across six keys, measured
in one process).

The larger cause is not the invented subject. It is the protocol:

> …when a fact is worth stating — **a parameter was refused**, nothing was written, a figure is
> missing — record it and DECLINE in the same answer.

> Write `RECORD: NONE` **if you will** put nothing on the record.

The first names the `permission_denied` situation as a fact worth recording. The second makes the
record discretionary. The key grades that discretion as determinate. On `permission_denied` the
recording rate is 82%; on `escalation_required`, 43%.

### Why it is parked and not fixed

**It affects disposition only.** `recorded_a_fact_where_none_was_expected` is not in
`_RESTRAINT_REASONS`, so no verdict failed on it. It caps a tier. At `propose` it is invisible; at
`auto_execute` it is not — and `auto_execute` is the target for every module.

**The fix voids the 21 September exams.** An ordered test for the record line is a protocol change
under ruling 1 above, so `RESPONSE_PROTOCOL_VERSION` moves to 7.0.0 and every 6.0.0 measurement
becomes non-comparable, including the six exams graded this evening and the 360-probe measurement
that found this. Keys naming a subject and a claim re-open Greenstone's 44 approved answer keys.

**Two candidate rewordings were measured and both moved the act.** Adding a constant
`RECORD: NONE` clause took recording to 47%; folding both branches into one sentence took it to
30%. Both dropped ESCALATE on `escalation_required` from 12/60 to 4/60, and the second put four
PROCEED into a class where the current wording has none. **A wording that fixes the record breaks
the act**, which is why this is disposition work and not a sentence edit.

### What parking means

It travels with the disposition work for `auto_execute`, alongside the three refusal acts and the
model question. It is not a defect to be fixed in passing, and the next person to find phi4
recording on a `RECORD: NONE` key should read this rather than re-measure it.
