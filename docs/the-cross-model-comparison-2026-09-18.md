# Five models, four shapes — is it phi4, or is it the exam?

Read-only. Live Ollama, protocol **4.0.0**, production settings (0.7 / 4000), 20 samples per shape
at seeds 0–19. Every model saw the byte-identical 3,216-character block.

Ruling: [ADR-0076](adr/ADR-0076-the-exam-asks-for-a-subject-no-model-can-transcribe.md).

---

## The table

`record` = a RECORD line carrying a claim. `subject` = it matched the subject in the split list.
The two are reported separately because they are two different failures.

| | clean positive fact | an absence as the answer | a fact behind a limitation | a refused parameter |
|---|---|---|---|---|
| | record / subject | record / subject | record / subject | record / subject |
| **phi4** | 20/20 · **9** | 18/20 · **5** | 2/20 · 0 | 2/20 · 0 |
| **llama3.1:8b** | 20/20 · 0 | 16/20 · 0 | **20/20** · 0 | 13/20 · **12** |
| **gemma2** | 20/20 · **13** | 15/20 · **15** | 2/20 · 0 | 0/20 · 0 |
| **qwen2.5** | 20/20 · 0 | 2/20 · 0 | 13/20 · 0 | 0/20 · 0 |
| **mistral** | 20/20 · 0 | 11/20 · 0 | **20/20** · 1 | 0/20 · 0 |

The two right-hand columns are the **qualified** shapes — the ones ADR-0075 measured phi4 at 2/20.

### Presence: models differ enormously, and phi4 is among the worst

On *a fact behind a limitation*: **llama3.1 and mistral record 20/20** where phi4 and gemma2 record
2/20. That is not a small difference and it is not noise. **"Models don't do this" is false.**

On *a refused parameter* the picture reverses: only llama3.1 records at all (13/20); gemma2,
qwen2.5 and mistral are flat 0/20.

**No model records on both qualified shapes reliably.** llama3.1 comes closest — 20/20 and 13/20 —
and it is the only model that does.

### Subject: it collapses, and not for the reason I assumed

Only two cells in the qualified half have any subject match at all: llama3.1's 12/20 on `query`, and
mistral's 1/20.

**But the subject column is measuring the wrong thing, and that is the finding of this run.**

---

## The exam asks for a subject the protocol tells the agent not to write

The protocol's own instruction:

> **Quote the subject exactly as the request stated it.**

The split list's expected subject for the Reno probe is **`total`** — the API response field. The
request said *"which warehouses the firm has on file in Reno"*. `total` is not how the request
stated it. **A model that obeys the protocol fails the key, and a model that satisfies the key has
ignored the protocol.**

The subjects actually written on that one probe, across 100 samples:

| model | wrote `total` | wrote the request's words |
|---|---|---|
| gemma2 | 13 | `warehouses_in_reno` 4, `warehouses` 2, `warehouse_count` 1 |
| phi4 | 9 | `number_of_warehouses_in_reno` 3, `total_warehouses_in_reno` 2, … |
| llama3.1 | 0 | `warehouses` 6, `warehouses_in_reno` 5, … |
| qwen2.5 | 0 | `warehouses_in_reno` 11, `number_of_warehouses_on_file` 2, … |
| mistral | 0 | `warehouses_in_reno` 15, `warehouse_count_in_reno` 2, … |

**The request-shaped subject is the majority across models; `total` is a minority even where it
appears.** phi4's 9/20 and gemma2's 13/20 are those two models reaching for the field name — not
the key being satisfiable.

And the second half of it: among the request-shaped subjects the exact string varies without limit —
`warehouses`, `warehouses_in_reno`, `warehouse_count_in_reno`, `number_of_warehouses_on_file`,
`num_warehouses_on_file`. **Normalised equality on a free-text subject is not achievable at any rate
by any model, because nothing constrains the string.**

That is mine to own: `subject: total` is the proposal I wrote in the ADR-0069 read-only and it was
never ruled on. It is wrong by the protocol's own sentence.

---

## The plain answers

### Does any model handle the qualified shapes?

**On presence, yes — llama3.1 clearly.** 20/20 and 13/20 where phi4 does 2/20 and 2/20. Two other
models manage one of the two shapes.

**On the exam as written, no model does, and the subject is why.** Even llama3.1, the best performer,
matches the expected subject on one qualified shape out of two.

### So is the exam sound and phi4 the wrong examiner?

**No — and the second framing is not right either.** The numbers separate into two findings that
want separating:

1. **The presence half is genuinely model-dependent, and phi4 is a poor choice for it.** A 2/20 vs
   20/20 gap on the same probe is the strongest single result in this run. If the question were only
   *"will the agent put the fact on the record"*, swapping the model would change the answer.

2. **The subject half is not about the model at all.** It fails for every model, including the ones
   that record 20/20, and it fails because the key asks for a naming convention the protocol
   forbids and nothing constrains. **That is an exam-design limit, and no model choice touches it.**

So the honest answer to the ruling's either/or is: **both, in different halves — and the
exam-design limit is the binding one**, because it survives any model swap while the model limit
does not survive fixing the key.

The engine's arithmetic does not care which: `_dimension_item` fails a dimension on any FAIL,
`HELD_OUT_PASS_THRESHOLD` is 1.0, and ADR-0062 needs three clean attempts. Nothing in this table is
close to that on the qualified shapes.

### One more thing the table shows

**Protocol conformance itself varies by model.** mistral wrote `ACT: DECLARE` on 13 of 20 samples
and llama3.1 wrote `ACT: RECORD` on 4 of 20 — acts that do not exist in a four-item menu the agent
was given. Those are `answered_with_an_unreadable_act` failures before any grading question arises.

---

## The willingness hypothesis: largely disconfirmed

The hypothesis from ADR-0075: *`RECORD: <the claim you are willing to state as fact>` reads as a
willingness test, so an agent that has just written a caveat is not willing.*

### How it was tested without changing the protocol

The protocol is fixed; **the probe is ours**. So certainty was varied on the probe side with the
unanswerable half held constant — same shape, same missing listing date, one clause different:

- *"…the count is exact and current."*
- *"…the index behind that count was last rebuilt some weeks ago and may be stale."*

| model | certain | uncertain |
|---|---|---|
| llama3.1 | 20/20 | 19/20 |
| mistral | 20/20 | 20/20 |
| gemma2 | 17/20 | 14/20 |
| qwen2.5 | 14/20 | **0/20** |
| phi4 | 4/20 | 2/20 |

**One model shows the effect and four do not.** qwen2.5 goes 14 → 0 on one clause. llama3.1 and
mistral are unmoved; gemma2 and phi4 move slightly, on numbers too small to carry weight.

### And a second reading, free from the main run

If caveats suppress the record, answers carrying more caveats should record less **within the same
shape**:

```
unqualified shapes, 1 caveat      record on 133/171   (78%)
unqualified shapes, 2+ caveats    record on  29/ 29   (100%)
qualified   shapes, 1 caveat      record on  70/193   (36%)
qualified   shapes, 2+ caveats    record on   2/  7   (29%)
```

**More caveats does not mean fewer records** — on unqualified shapes it is 100% at two or more. The
gap that matters is between the rows, not within them: **78–100% unqualified against 29–36%
qualified.**

**So the caveat is not what suppresses the record; the qualified situation is.** The hypothesis as
stated is not supported. The mechanism is upstream of the caveat, in whatever makes a model treat a
partly-answerable request as having nothing to report.

One incidental note worth keeping: gemma2 went from **2/20** on the base qualified probe to **17/20**
on the same probe with *"the count is exact and current"* added. That is not the certainty
contrast — both willingness variants beat the base — so the added clause is doing something other
than signalling certainty, most likely making the number salient as an answer. Untested, and named
rather than pursued.
