# ADR-0074 — The third worked example, and F1 settled

**Status:** accepted · **Decided by:** Ivan Green, 18 September 2026 · **Built by:** the coordinator
**Follows:** [ADR-0073](ADR-0073-the-decline-gloss-is-corrected.md), which measured the words and
found them insufficient.

---

## The rulings

**1. F1 — take the 3/3 mix.** *`property_lookup` reads only; almost everything that goes wrong with
it is a success that is quietly incomplete. Re-class ⓑ, ⓒ and ⓓ to `partial_failure`. **The
criterion is what the scenario tests, not where the fact was written down; where the two disagree,
what it tests wins.***

**2. The words are not the binding constraint; the examples are.** *Measured: the corrected gloss
changed nothing, 0 of 20 both ways. The protocol carries a third worked example showing DECLINE with
a real record. Until it does, any scenario expecting that shape is untestable.*

---

## Ruling 1 — the criterion, settled

The open question from ADR-0073 is closed, and closed with a general criterion rather than a
per-scenario call: **what the scenario tests wins over where the fact was written down.**

That resolves the case I could not, and which I flagged against myself. Fact ⓑ — reading back a
silently capped `page_size` — is cited to `inputs`, not to `failure_signatures`, so the citation
criterion and the competency reading pointed in opposite directions. Ruling 1 says the competency
reading wins, which makes the criterion applicable rather than something to be argued case by case.

`property_lookup` becomes **3 `happy_path` / 3 `partial_failure`**. Its `failure_recognition` score
no longer rests on the single `total: 0` scenario, and that is the faithful weighting for a pure
read whose failure mode is a `200` that is less than it looks.

Nothing to build: this is a change to The Office's five approved keys.
[the-split-list.md](../the-split-list-under-the-rulings-2026-09-18.md) carries the proposal; under
ruling 1 its Group-2 F1 entry is now a decision.

## Ruling 2 — built, and it did not work

The third example is in the block: `ACT: DECLINE` with a real record, sitting second, beside the
other DECLINE so the discriminating variable is adjacent.

**Measured: 0 of 20 under two examples, 0 of 20 under three.** The same result the words alone gave.

Ivan's ruling stands regardless — *until the protocol carries it, any scenario expecting that shape
is untestable* — and the protocol now carries it. But it does not yet produce the shape, and the
three measurements are in [the-third-example.md](../the-third-example-2026-09-18.md).

### What the diagnostic found

A second probe, where the agent plainly **holds** a fact (7 warehouses, no listing date to filter
on):

- **The agent under-uses the RECORD line generally** — 5/20 and 2/20 record anything at all. The
  failure is not specific to `DECLINE`; that pairing is its sharpest instance.
- **The third example moved the ACT: `DECLINE` 1/20 → 14/20.** Far outside the noise band, and the
  one effect the examples were explicitly built not to have. The block now shows `DECLINE` in two of
  three examples, and the agent copied the act without the pairing it was there to demonstrate.

Arguably not harm — spurious `REFUSE` fell 11/20 → 4/20 on a probe with no prohibition in play. But
it is the examples steering the act, and the existing guard only asserts a *copy* of an example
fails a never-do probe. Nothing asserted that the example set leaves the act distribution alone, and
nothing measured it until now.

**Stopping here, as ruled.** No fourth example.

### The version bump: MAJOR, `3.1.0` → `4.0.0`

The same test every earlier major was taken on: *the block changed shape.* A third worked answer is
a part gained, not a description corrected — and measurement C shows it is a shape change in effect
as well as in form.

**Non-comparable from here:** everything under 3.0.0 and 3.1.0, including the six Greenstone
verdicts, the 8 → 0 RECORD result, and both of ADR-0073's 0/20 results.

3.1.0 stays as the counter-case: minor when the grammar's *description* was corrected, major when
the block gained a part.

## A claim withdrawn

ADR-0073 reported the 16 held-out probes as **"identical, probe for probe"**. That is stronger than
the instrument supports and is withdrawn.

Running the *same* text twice in one process, at the same seeds, differs on one probe. A single
request repeated is byte-identical, so the model is deterministic per call; the 16-probe *sequence*
is not, and probe 0 — where cache state differs between a cold arm and a warm one — is where it
moves.

**A 16-probe run at n=1 cannot resolve a difference of one or two probes.** ADR-0073's ruling is
unaffected: minor rested on the grammar argument and stands on its own. Its evidence was overstated,
and the honest version is that no systematic difference was detected, and none could have been at
that resolution.

Recorded here rather than edited into ADR-0073, because a recorded result's basis is not rewritten —
the rule this repository has now applied to a stored number, a labelled measure, and its own prose.

## What this does not decide

Why the RECORD line is under-used generally. Whether the example set should be rebalanced so two of
three do not show the same act. Whether the guard should assert that examples leave the act
distribution alone — it now has a measurement to assert against, which it did not before.
