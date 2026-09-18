# ADR-0075 — The RECORD line is a model finding, and wording changes stop

**Status:** accepted · **Decided by:** Ivan Green, 18 September 2026 · **Nothing built.**
**Follows:** [ADR-0074](ADR-0074-the-third-worked-example.md), whose diagnostic produced the number.

---

## The ruling

**The RECORD line is under-used by phi4 in general, measured at 2–5 of 20 on a probe where the fact
is unmissable. That is a finding about the model, not the wording. Wording changes stop here until
it is understood.**

---

## Why it is the right place to stop

Two wording changes were built and measured, and neither moved the behaviour:

```
ADR-0073   the DECLINE gloss corrected, words only          0/20 both texts
ADR-0074   a third worked example, the shape demonstrated   0/20 both texts
```

A third would have been the third attempt at the same explanation. The ruling names the one that is
left: **the model, not the text.**

It also draws a line this repository has drawn before in other forms — a measurement that keeps not
moving is evidence about the thing being measured, and continuing to adjust the instrument is how a
null result gets talked out of existence.

## What was measured after the ruling

Read-only, and it refines the ruling's own number rather than merely confirming it. Full report in
[the-record-line-and-phi4.md](../the-record-line-and-phi4-2026-09-18.md).

**The rate is not one number.** 20 samples per shape, live phi4, protocol 4.0.0:

| shape | record present | subject matches |
|---|---|---|
| clean positive fact | **20/20** | 9/20 |
| an absence as the answer | **18/20** | 5/20 |
| a fact behind a limitation | **2/20** | 0/20 |
| a refused parameter | **2/20** | 0/20 |

**phi4 records readily when the answer is a clean assertion, and almost never when it is qualified.**
The 2–5 of 20 in the ruling is the qualified case; the clean case is 20 of 20.

**And a second failure channel nobody had measured: the subject.** Even at 20/20 presence, only 9/20
wrote the expected subject. The rest invented one — and once copied the literal template, angle
brackets and all.

**What it does instead is put the fact in a CAVEAT** — a conforming answer with the fact demoted one
line. Not prose, not silence. Three captured verbatim in the report.

## The consequence for the 41 scenarios

**33 of 41 expect a record. About 25 of those 33 would fail today**, and the exam is not passable by
phi4 on any module — `_dimension_item` fails a dimension on any FAIL, `HELD_OUT_PASS_THRESHOLD` is
1.0 and its own comment says it is not a knob, and ADR-0062 requires three clean attempts. Every
module contains at least one scenario of the shape measured at 0 of 20.

Even grading on record *presence* alone and discarding the subject channel, the best module's chance
of passing three attempts is about **1 in 1,400**.

**What that is not.** It is not a finding that phi4 cannot operate these modules. Every captured
answer is a good answer: it refuses correctly, names the limitation accurately, attaches the right
caveats. It is a finding that the exam measures a reporting format the model does not use for
qualified answers, and that the exam is all-or-nothing.

## What stays open

Five ways the behaviour could be moved are laid out in the report with their costs and what each
makes non-comparable — reordering the answer, a system-prompt reminder, a re-prompting check, naming
the failure, and a different model. **No recommendation is made and none is built.**

Two things in that list are worth carrying forward whichever is chosen:

- **A reminder placed in `battery_system_context` outside the protocol block is stamped by neither
  `RESPONSE_PROTOCOL_VERSION` nor `PROMPT_VERSION`** — a change to the exam that no version records.
  That gap wants closing first.
- **"Refuse an answer with no RECORD line" does not do what it sounds like.** A missing RECORD line
  is already a violation; what is happening is `RECORD: NONE`, which conforms. Making that a named
  failure costs nothing and moves nothing — it changes what the failure is called.

And the question the ruling actually holds open: **are the 41 scenarios unpassable by this exam, or
unpassable by this model?** Six models were measured under protocol 1.0.0 at record rates from 3/11
to 11/11, so the behaviour is strongly model-dependent — but those runs used a different protocol,
module, probe set and question, and cannot be quoted as an answer. What a comparison would take is
sized in the report. It was not run.
