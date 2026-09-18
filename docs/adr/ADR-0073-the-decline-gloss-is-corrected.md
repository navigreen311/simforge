# ADR-0073 — The DECLINE gloss is corrected to match the grammar

**Status:** accepted · **Decided by:** Ivan Green, 18 September 2026 · **Built by:** the coordinator
**Follows:** [ADR-0072](ADR-0072-breadth-is-its-own-rule.md), whose flag **F4** raised it.

---

## The rulings

**1. The DECLINE gloss is corrected to match the grammar.** *It says "there is nothing to report"
while the grammar allows a record beside a DECLINE, and seven scenarios expect exactly that.
Correcting a sentence that misdescribes the grammar is not a new exam.*

**2. F2, F3, F5 and F6 accepted as proposed.**

**3. F4's ACT for `underwrite_deal / recovery_after_failure` is DECLINE** — *it tried, failed, and
reports rather than hands off.*

**4. F1 is not settled.** *Re-classing by instruction section is a reasonable criterion but it is
Claude's, not Ivan's, and it re-weights `property_lookup` from 1/1 to 3/3.*

---

## Ruling 1 — built

The block's grammar has always been two independent choose-ones: one ACT from four, one RECORD from
two. The prose gloss on DECLINE said *"there is nothing to report"*, which reads as a rule that a
declined request records nothing — and it is not one.

Two edits, both subtractions plus one added line. The before and after as the agent sees it, and the
measurement, are in [the-decline-gloss.md](../the-decline-gloss-2026-09-18.md).

**Why it mattered now.** Under ADR-0072's rulings, seven scenarios across the five approved keys
expect a DECLINE **with** a record: the five `malformed_input` scenarios and both
`underwrite_deal` recoveries. An agent obeying the gloss writes `RECORD: NONE` and fails a scenario
it had understood perfectly — a grader marking down the protocol's own mistake.

### The version bump: MINOR, `3.0.0` → `3.1.0`

The first minor on this stamp, and the digit is load-bearing.

- **A bump at all**, because the text changed and the stamp's job is to say which text produced a
  measurement. Two different texts must not be indistinguishable in the record.
- **Minor**, because the grammar did not move — same four acts, same two RECORD forms, same counts,
  same separator, same two examples. A sentence that *described* the grammar incorrectly was
  corrected to match it, and that cannot make a prior measurement wrong.
- **And minor is a claim, so it was measured.** A major bump asserts *prior results are not
  comparable*. The 16 held-out probes were run under both texts at seed 0 and came back
  **identical** — probe for probe, including the one surviving two-ACT violation. Everything
  measured under 3.0.0 still stands: the six Greenstone verdicts, the 8 → 0 RECORD result, the
  16/16 parse runs.

## The finding the measurement produced

**The correction did not move the case it is about.** A purpose-built probe where DECLINE-with-a-
record is the right answer, 20 samples per text: **0/20 under the old text, 0/20 under the new.**

The reason is the examples, not the words. The block carries two worked answers and they demonstrate
exactly the pairing the gloss used to assert — `DECLINE` → `NONE`, `PROCEED` → a claim. An agent
holding a rule that says *"any act may be followed by either RECORD form"* and two instances that
say otherwise follows the instances.

**A third worked example is the obvious next change and is deliberately not here.** It changes the
block's shape rather than correcting a description of it, which is a MAJOR bump by the rule stated
beside the constant, and it wants measuring on its own. One change at a time — the ruling that has
held since ADR-0068.

Trimming four words off the first example's caveat (*"…, so there is nothing to report"*) is as far
as this goes. That sentence was true of its example and still taught the wrong rule.

## Rulings 2 and 3 — recorded

Applying to The Office's five approved keys; nothing to build here.

| | |
|---|---|
| **F2** | `comp_analysis` does not grow — its `escalation_required` split produces a duplicate of its own `happy_path`, so the scenario narrows to its ESCALATE half. 5 → 5. |
| **F3** | `malformed_input` on the two writers records the write-certainty: `contract_created = NO`, `deal_analysis = NOT WRITTEN`. Q6 extends past `permission_denied`. |
| **F5** | `assign_contract` rows 2 and 5 both carry `sent = false`, in different situations. Kept. |
| **F6** | `underwrite_deal / happy_path` ⓐ stays `happy_path` despite citing two sections. |
| **F4** | `underwrite_deal / recovery_after_failure` is **DECLINE** on both rows — *it tried, failed, and reports rather than hands off.* |

F4's ruling draws the line the `malformed_input` ruling implied: **ESCALATE is for when a person's
authority is needed**, not for any answer a person will end up reading. A recovery that retried, was
licensed to retry, failed, and reports a stale row needs nobody's permission.

And it is the second place the grammar now expects a DECLINE with a record — `reanalysis = FAILED`
and `deal_analysis = STALE, written <date>` — which is why ruling 1 travels with it.

## Ruling 4 — F1 stays open

The re-class criterion is unsettled and the split list still carries my proposal rather than a
decision. The three `property_lookup / happy_path` facts proposed to move, each with its reasoning
and what it would test where it lands, are in
[the-property-lookup-reclass-question.md](../the-property-lookup-reclass-question-2026-09-18.md),
with both class mixes and what each measures.

## What this does not decide

Whether a third worked example is added, and at what version. F1. Whether the `ESCALATE` gloss wants
the same treatment — it says *"handing the request to a person instead of answering it"*, and under
Q6 two `permission_denied` scenarios now escalate **and** record, which is not quite "instead".
Noted rather than changed: one change at a time, and that one is not yet blocking a scenario.
