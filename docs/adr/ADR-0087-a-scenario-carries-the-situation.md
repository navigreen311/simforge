# ADR-0087 — A submitted scenario carries the situation

**Status:** accepted · **Decided by:** Ivan Green, 19 September 2026 · **Built.**
**Follows:** [ADR-0086](ADR-0086-the-runner-grades-by-transcription.md), whose build found the gap.

---

## The ruling

**A submitted scenario carries the situation the agent is asked. SimForge declares it first, per the
ordering its own `extra="forbid"` imposes.**

---

## The ordering, which is the part worth keeping

Since [ADR-0083](ADR-0083-a-boundary-that-ignores-is-not-a-boundary.md) an undeclared field is
**refused**, not dropped. That closed a real hole and it also fixed a direction: **the sender can no
longer go first.** A field The Office invents and sends now gets a 422 instead of silence.

So the protocol between the two systems is: **the receiver declares, then the sender fills.** This
is the first change made under that ordering, and it is why SimForge adds a column for a field
nothing yet sends.

## Built

`situation` on the payload, on the row, in the write, and `probe_for(key)` in the runner.

**`probe_for` renders the situation and nothing else.** Two deliberate omissions:

- **Never `expected_behavior`.** That is what a good *answer* looks like; putting it to the agent
  would hand over the answer. It is the same reason The Office refuses to send the situation in
  that field.
- **Not ADR-0077's naming sentence**, and that is timing rather than oversight. Its whole safety
  argument is that the sentence is **identical on every probe including the held-out ones** —
  otherwise its presence says a record is expected, and on a `never_do_violation` probe that leaks
  the class. Adding it to submitted probes alone would create exactly that tell. It lands on both
  halves at once, with the protocol bump, or not at all.

## Absent: refused, or NOT_RUN?

**NOT_RUN, and two arguments point the same way.**

**A required field would refuse every curriculum The Office sends today.** Its generator holds the
situation in `summary` and does not send it, so `NOT NULL` would 422 Gate 8 for a venture that is
already certifying. Declare first, require later — and the flip to required is a decision for the
day The Office is sending it, not an automatic consequence.

**And when it is absent the fault is the submitter's, not the agent's.** Nothing was asked, so no
answer in hand is an answer to this key. Grading it FAIL would put an omission in the curriculum
onto the agent's record — the same rule a missing `expected_answer` already follows.

Both are tested: a submission without a situation is **accepted**, and its scenario grades
**NOT_RUN** carrying `the_submission_carried_no_situation`.

### Its own reason, and its own place in the order

Distinct from `the_scenario_was_never_put`, and **the distinction is who has work to do**: a probe
that was not put is a runner problem; a scenario with no situation is a submitter problem. Only a
named reason each makes that visible.

**The check runs before `answer is None`**, and the order was a bug the tests caught. With no
situation there was nothing to run, so `the_scenario_was_never_put` would name a runner that had
nothing to put. The submitter's omission is the primary fact and must not hide behind a reason that
reads as somebody else's.

### And it caught its own fixture

Adding the rule turned fourteen existing tests red, because the shared `_key()` helper had no
situation — every grading test was exercising a key that, under the new rule, has nothing to ask.
The fixture was under-specified and is now explicit. That is twice this week a new rule's first act
was to catch a fixture describing a run it did not have.

## Read-only alongside

[The eleven that count for nothing](../the-eleven-that-count-for-nothing-2026-09-19.md) — five
options for the `malformed_input` and `permission_denied` scenarios, with what each would claim
about an agent. Nothing recommended.
