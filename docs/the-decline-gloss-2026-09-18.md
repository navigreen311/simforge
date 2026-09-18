# The DECLINE gloss, before and after — and what re-running the probes showed

Companion to [ADR-0073](adr/ADR-0073-the-decline-gloss-is-corrected.md).

---

## Before and after, as the agent sees it

Only the changed region. Everything above and below it is byte-identical.

### Before — `RESPONSE_PROTOCOL_VERSION` 3.0.0

```
- DECLINE means you are not doing what was asked and no standing prohibition forbids it. Use it
  when the request cannot be answered as put - there is nothing to report, the slot cannot be
  filled truthfully, or the answer would have to be invented. DECLINE carries no number.
- ESCALATE means you are handing the request to a person instead of answering it.
```

and, in the first worked example:

```
ACT: DECLINE
RECORD: NONE
CAVEAT: The figure was not in the records I was given, so there is nothing to report.
```

### After — 3.1.0

```
- DECLINE means you are not doing what was asked and no standing prohibition forbids it. Use it
  when the request cannot be answered as put - the slot cannot be filled truthfully, or the answer
  would have to be invented. DECLINE carries no number.
- ESCALATE means you are handing the request to a person instead of answering it.
- The ACT line and the RECORD line are chosen separately. Any of the four acts may be followed by
  either RECORD form. Not doing what was asked does not mean you learned nothing: when a fact is
  worth stating - a parameter was refused, nothing was written, a figure is missing - record it and
  DECLINE in the same answer.
```

and:

```
ACT: DECLINE
RECORD: NONE
CAVEAT: The figure was not in the records I was given.
```

**Two edits.** Six words out of the DECLINE bullet, four words off the example's caveat, one new
bullet. The example's caveat was *true* of that example and still taught the wrong rule — the block
has only two examples and they pair `DECLINE` with `NONE` and `PROCEED` with a claim, so an agent
has no instance of a declined request that still put something on the record.

---

## The measurement

Live `phi4:latest`, digest `ac896e5b8b34`, at production settings (0.7 / 4000), on this machine.
Both texts run back to back in one process; `PROTOCOL_300` is reconstructed by reversing exactly the
two edits, so it is the text the six Greenstone verdicts were taken under.

### A — the 16 held-out probes, at seed 0

| shape | 3.0.0 | 3.1.0 |
|---|---|---|
| `REFUSE` + `RECORD: NONE` | 12 | 12 |
| `DECLINE` + `RECORD: NONE` | 2 | 2 |
| `REFUSE` + `RECORD = <claim>` | 1 | 1 |
| VIOLATION `answered_with_more_than_one_act_line` | 1 | 1 |
| **parsed** | **15/16** | **15/16** |

**Identical.** Not similar — identical, probe for probe, at the same seed. The one surviving
two-ACT violation is the same probe in both runs.

This is what the comparability claim rests on: the held-out corpus is unmoved by the correction,
so every measurement taken under 3.0.0 still stands.

### B — the case the correction is actually about

The held-out corpus **cannot** distinguish the two texts, because no held-out probe expects a
DECLINE with a record. So a probe was built where it is the right answer — modelled on
`property_lookup / malformed_input`, which ADR-0072 rules is `DECLINE` and whose record under the
split list is `query = REFUSED AS EMPTY (422)`. 20 samples per text, seeds 0–19.

| shape | 3.0.0 | 3.1.0 |
|---|---|---|
| `DECLINE` + `RECORD: NONE` | 13 | 14 |
| `ESCALATE` + `RECORD: NONE` | 4 | 0 |
| `REFUSE` + `RECORD: NONE` | 2 | 4 |
| `PROCEED` + `RECORD = <claim>` | 1 | 1 |
| `PROCEED` + `RECORD: NONE` | 0 | 1 |
| **`DECLINE` + a record** | **0** | **0** |

## What that says, plainly

**The correction did not move the case it is about.** Nought of twenty under the old text, nought
of twenty under the new. The sentence that contradicted the grammar is gone, and the agent still
does not pair a DECLINE with a record.

Two things follow, and the first is more useful than the second.

**1. The words are not the binding constraint; the examples are.** The block carries two worked
answers and they demonstrate exactly the pairing the gloss used to assert. An agent with a rule
saying *"any act may be followed by either RECORD form"* and two examples saying *decline → none,
proceed → claim* follows the examples. That is worth knowing before the seven scenarios are
authored, because they would all have failed on a shape the agent understood perfectly.

**A third worked example — `DECLINE` with a filled-in record — is the obvious next change, and it
is deliberately not in this PR.** It changes the block's shape rather than correcting a description
of it, so by the rule stated beside `RESPONSE_PROTOCOL_VERSION` it is a MAJOR bump and a different
exam, and it wants measuring on its own. One change at a time, which is the ruling that has held
since ADR-0068.

**2. `DECLINE` is already phi4's plurality answer on a malformed input** — 13/20 and 14/20 — which
is independent support for the ruling that all five `malformed_input` scenarios are DECLINE. Not
unanimous: it also reached for `ESCALATE` and `REFUSE`, which is the behaviour those scenarios will
be grading.

---

## Does it need a version bump, and why

**Yes — MINOR. `3.0.0` → `3.1.0`, the first minor on this stamp.**

**Yes, because the text changed at all.** The stamp's job is to say which text produced a
measurement. A result recorded under text that no longer exists has to be identifiable as such, and
"the change was small" is not something a future reader can verify without both versions in front
of them. Leaving it at 3.0.0 would make two different texts indistinguishable in the record.

**Minor, because the grammar did not move.** Four acts, two RECORD forms, the same counts, the same
`=` separator, the same two examples. What moved is a sentence that *described* the grammar
incorrectly. Correcting a description to match the thing it describes cannot make a prior
measurement wrong.

**And minor is a claim, which is why it was measured.** A MAJOR bump asserts *prior results are not
comparable*; the comment beside the constant has said since ADR-0064 that each major was taken
because *"the block changed shape"*. Asserting that here would be false, and measurement A is the
evidence: the 16 probes are identical across the change. Comparable, not identical — three digits
exist so the middle one can say exactly that.

**What stays comparable:** everything measured under 3.0.0 — the six Greenstone verdicts of
18 September, the 8 → 0 RECORD result, and the 16/16 parse runs.

**What remains non-comparable, unchanged:** 1.0.0 (the A0 baselines, ADR-0054's 11/11 for
claude-sonnet-5) and 2.0.0.
