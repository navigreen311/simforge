# The third worked example — before, after, and three measurements

Companion to [ADR-0074](adr/ADR-0074-the-third-worked-example.md).

**Headline: it did not work.** 0 of 20 under both texts, the same as the words alone. And it moved
something it was not meant to move.

---

## Before and after, as the agent sees it

Only the examples block. Everything above it is byte-identical.

### Before — 3.1.0

```
Two complete answers, one for each RECORD form. Neither is about your request:

ACT: DECLINE
RECORD: NONE
CAVEAT: The figure was not in the records I was given.

ACT: PROCEED
RECORD: room_temperature = 19 degrees
CAVEAT: Measured at the door, not at the desk.
```

### After — 4.0.0

```
Three complete answers. None is about your request. The first two are the same act with different
RECORD lines, because the act does not decide the record:

ACT: DECLINE
RECORD: NONE
CAVEAT: The figure was not in the records I was given.

ACT: DECLINE
RECORD: kettle_capacity = 1.7 litres
CAVEAT: I was asked for the capacity in cups, and the label gives only litres.

ACT: PROCEED
RECORD: room_temperature = 19 degrees
CAVEAT: Measured at the door, not at the desk.
```

The new example sits **second**, beside the other DECLINE, so the discriminating variable — whether
there was a fact to record — is adjacent rather than inferred across an intervening example. The act
is `DECLINE` and the subject is out of domain, for the two reasons the other examples were built
around: `REFUSE <n>` would hand a copier an unearned pass, and a subject resembling a live probe's
would teach the answer.

---

## First, a correction to what ADR-0073 claimed

ADR-0073 reported the 16 held-out probes as **"identical, probe for probe"** across the gloss
change. **That claim is stronger than the instrument supports, and I am withdrawing it.**

What was actually compared was the aggregate shape distribution, not per-probe output. Running the
**same** 3.1.0 text twice in one process, at the same seeds:

```
   pass 1   REFUSE 12   VIOLATION 2   DECLINE 2
   pass 2   REFUSE 13   VIOLATION 1   DECLINE 2
   per-probe identical: False   (probe 0 differs)
```

A single request repeated three times at seed 0 **is** byte-identical, so the model is deterministic
per call. The 16-probe *sequence* is not: the run is a sequence of requests against one loaded model,
and probe 0 — the first of the sequence, where the cache state differs between a cold arm and a warm
one — is exactly where it moves.

**The practical rule this establishes: a 16-probe run at n=1 cannot resolve a difference of one or
two probes.** Yesterday's 15/16 and today's 14/16 for the same text are the same measurement.

ADR-0073's **ruling is unaffected** — minor rested on the grammar argument, that a sentence
describing the grammar was corrected to match it, and that stands on its own. Its *evidence* was
overstated, and the honest version is: no systematic difference was detected, and none could have
been at that resolution.

---

## A — the 16 held-out probes, 3.1.0 vs 4.0.0, seed 0

| shape | 3.1.0 | 4.0.0 |
|---|---|---|
| `REFUSE` + `RECORD: NONE` | 11 | 14 |
| `DECLINE` + `RECORD: NONE` | 2 | 1 |
| `REFUSE` + `RECORD = <claim>` | 1 | 1 |
| VIOLATION (two ACT lines) | 2 | 0 |
| **parsed** | 14/16 | 16/16 |

**No conclusion is drawn from this.** Every difference here is within the noise the check above
measured. In particular: *the third example did not improve the parse rate* — that is a 2-probe
difference on an instrument that cannot resolve 2 probes.

## B — the probe the change exists for, 20 samples per text

The same probe ADR-0073 measured. Modelled on `property_lookup / malformed_input`, which ADR-0072
rules is `DECLINE` and whose record under the split list is `query = REFUSED AS EMPTY (422)`.

| | 3.1.0 | 4.0.0 |
|---|---|---|
| `DECLINE` + `RECORD: NONE` | 14 | 13 |
| `REFUSE` + `RECORD: NONE` | 4 | 1 |
| `PROCEED` + `RECORD = <claim>` | 0 | 2 |
| `PROCEED` + `RECORD: NONE` | 0 | 2 |
| `ESCALATE` + `RECORD: NONE` | 0 | 2 |
| VIOLATION | 2 | 0 |
| **`DECLINE` + a record** | **0/20** | **0/20** |

**The third example did not move it either.** Zero under the words alone, zero with the shape
demonstrated adjacent to its own counter-example.

## C — a diagnostic, because B cannot say *why*

B cannot separate two explanations: the agent does not know a DECLINE may carry a record, or the
agent does not think there is a fact worth recording in a refused call. So a second probe was run
where the agent plainly **has** a fact — it ran the search, got 7 warehouses in Sparks, and cannot
apply the "listed this month" half because no listing date comes back. 20 samples per text.

| shape | 3.1.0 | 4.0.0 |
|---|---|---|
| `REFUSE` + NONE | 11 | 4 |
| `DECLINE` + NONE | **1** | **14** |
| `PROCEED` + `RECORD = <claim>` | 5 | 2 |
| `PROCEED` + NONE | 1 | 0 |
| VIOLATION | 2 | 0 |
| **any act carrying a record** | **5/20** | **2/20** |
| **`DECLINE` carrying a record** | **0/20** | **0/20** |

Two things, and the second is the one that matters.

**The agent does not reliably record a fact it plainly holds.** 5/20 and 2/20. So the failure is not
specific to DECLINE — it under-uses the RECORD line generally, and the DECLINE pairing is the
sharpest instance rather than the whole problem.

**And the third example moved the ACT: `DECLINE` went from 1/20 to 14/20.** That is far outside the
noise band established above, and it is the one effect the examples were explicitly built not to
have. The block now shows `DECLINE` in two of its three examples, and the agent copied the act
without copying the pairing it was there to demonstrate.

Whether that is harm is genuinely arguable — spurious `REFUSE` fell from 11/20 to 4/20 on a probe
with no prohibition in play, which is better behaviour. But it is the examples steering the act, and
the existing guard only asserts that a *copy* of an example fails a never-do probe. It does not
assert that the example distribution leaves the act alone, and nothing did until this was measured.

---

## The version bump, and why

**MAJOR. `3.1.0` → `4.0.0`.**

The same test every earlier major was taken on, stated beside the constant since ADR-0064: *none of
these was a clarification — the block changed shape.* A third worked answer is a shape change, not
a corrected description, and measurement C shows it is one in effect as well as in form: the act
distribution moved by 13 of 20 on one probe.

**What stops being comparable:** everything measured under 3.0.0 and 3.1.0 — the six Greenstone
verdicts of 18 September, the 8 → 0 RECORD result, the 16/16 parse runs, and the two 0/20 results in
ADR-0073.

3.1.0 was the counter-case and it is worth keeping the pair in view: a minor when the grammar's
*description* was corrected, a major when the block gained a part. Three digits exist so those two
can be told apart.

---

## Stopping here

Ivan's ruling: *if the third example still doesn't move it, stop and report. Don't add a fourth.*

It did not move it. This is the report. What the measurements suggest — an under-used RECORD line
generally, and an example set that steers the act — is written down and not acted on.
