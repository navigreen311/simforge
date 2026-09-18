# ADR-0076 — The exam asks for a subject the protocol forbids, and no model can transcribe it

**Status:** accepted · **Decided by:** Ivan Green, 18 September 2026 · **Nothing built.**
**Follows:** [ADR-0075](ADR-0075-the-record-line-is-a-model-finding.md), which held everything until
this was measured.

---

## The ruling

**Before any further wording, protocol or design change, measure whether this is a phi4 limit or an
exam-design limit. Nothing else moves until that is known.**

---

## What was run

Five installed local models — `phi4`, `llama3.1:8b`, `gemma2`, `qwen2.5`, `mistral` — against four
shapes, 20 samples each, protocol 4.0.0, production settings, identical block to every model. Plus
the willingness test from ADR-0075, designed so it needs no protocol change. ~600 calls, six minutes.

Full table: [the-cross-model-comparison.md](../the-cross-model-comparison-2026-09-18.md).

## The answer: both, in different halves — and the exam-design limit is the binding one

### 1. The presence half is a model limit, and phi4 is a poor choice for it

On *a fact behind a limitation*:

```
llama3.1   20/20        mistral   20/20        qwen2.5   13/20
phi4        2/20        gemma2     2/20
```

A 2/20 against 20/20 gap on the same probe with the same block. **"Models don't do this" is false** —
it is the strongest single result in the run. If the question were only *will the agent put the fact
on the record*, the model choice would settle it.

No model manages **both** qualified shapes; llama3.1 comes closest at 20/20 and 13/20 and is the
only one that records on the refused-parameter shape at all.

### 2. The subject half is not about the model, and it is the binding constraint

**The protocol says: *"Quote the subject exactly as the request stated it."*** The split list's
expected subject is `total` — an API response field. The request said *"which warehouses the firm
has on file in Reno"*.

**A model that obeys the protocol fails the key; a model that satisfies the key has ignored the
protocol.** Across 100 samples on that probe, the request-shaped subject is the majority and `total`
is a minority even where it appears. And among the request-shaped subjects the exact string varies
without limit — `warehouses`, `warehouses_in_reno`, `warehouse_count_in_reno`,
`number_of_warehouses_on_file`.

**Normalised equality on a free-text subject is not achievable at any rate by any model, because
nothing constrains the string.** That is an exam-design limit and no model swap touches it.

**It is mine to own.** `subject: total` is the proposal I wrote in the ADR-0069 read-only; it was
never ruled on, and it is wrong by the protocol's own sentence.

### 3. Which means the either/or in the ruling resolves this way

The model limit is real and fixable by choosing a different model. The design limit survives any
model choice. **So the design limit binds**, and the presence finding only becomes actionable after
it is settled.

### 4. And a third thing the table showed

**Protocol conformance itself varies by model.** `mistral` wrote `ACT: DECLARE` on 13 of 20 samples;
`llama3.1` wrote `ACT: RECORD` on 4 of 20 — acts absent from a four-item menu the agent was handed.
Those fail before any grading question arises, and they are a reason a model swap is not a one-line
decision.

## The willingness hypothesis is largely disconfirmed

Tested **without touching the protocol**: the probe is ours, so certainty was varied on the probe
side with the unanswerable half held constant.

```
              certain   uncertain
llama3.1        20/20       19/20
mistral         20/20       20/20
gemma2          17/20       14/20
qwen2.5         14/20        0/20
phi4             4/20        2/20
```

One model of five shows the effect. And the second reading, free from the main run — caveat count
against record presence, within shape class — points the other way: 100% of unqualified answers
carrying two or more caveats still record. **The caveat is not what suppresses the record; the
qualified situation is.**

So the hypothesis as stated is wrong. Whatever makes a model treat a partly-answerable request as
having nothing to report sits upstream of the caveat.

## What stays held

ADR-0075's hold is satisfied — the question it asked is answered — and nothing is built here.

The decisions the numbers now put in front of Ivan, none of them recommended:

- **The expected subject.** A free-text subject cannot be transcribed. Either the probe supplies a
  closed vocabulary the agent picks from, or subject matching is dropped and the claim is graded
  alone, or the key stops using field names and quotes the request as the protocol requires — which
  still leaves the string unconstrained.
- **The examiner model**, which only matters once the subject is settled, and which ADR-0061 makes a
  decision about what the Village runs rather than about SimForge.
- **The all-or-nothing arithmetic.** `_dimension_item` fails a dimension on any FAIL and
  `HELD_OUT_PASS_THRESHOLD` is 1.0 and not a knob. Nothing in this table is close to that on the
  qualified shapes, whichever model sits the exam.
