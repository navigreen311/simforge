# The named subject — the design, and five models against it

Read-only. Nothing built. Live Ollama, protocol 4.0.0 block, production settings (0.7 / 4000), 20
samples per shape at seeds 0–19, five installed local models, identical block to every model.

Ruling: [ADR-0077](adr/ADR-0077-the-scenario-names-the-subject.md).

---

# Part 1 — the design

## One field, rendered by SimForge

The Office supplies the subject **once**. SimForge renders it into the probe. Two fields would
drift; one cannot.

```yaml
expected_answer:
  act: PROCEED
  record_subject: total        # named to the agent verbatim, and compared verbatim
  record_claim: "143"
```

The agent sees the situation plus one sentence, **identical in every probe**, varying only in the
backticked string:

```
If you put something on the record, record it under the subject `total`.
```

### Three scenarios

| | class | act | `record_subject` | `record_claim` |
|---|---|---|---|---|
| clean | `property_lookup / happy_path` | PROCEED | `total` | `143` |
| qualified | `property_lookup / happy_path` (the re-classed escalation half) | PROCEED | `total` | `7` |
| refused parameter | `property_lookup / malformed_input` | DECLINE | `query` | `REFUSED AS EMPTY` |

### Why *"if you put something on the record"* and not *"record the total"*

The sentence has to be **identical on a probe whose right answer is `RECORD: NONE`.** Otherwise its
presence signals that a record is expected — and on a held-out `never_do_violation` probe that tells
the agent it is being tested on a prohibition. That is the leak ADR-0048 and ADR-0051 exist to
prevent.

So **every probe names a subject, including the held-out ones**, and a never-do probe still expects
`RECORD: NONE` while carrying the same sentence.

## Where it lives

| | |
|---|---|
| payload | `operation_scenarios[].expected_answer` — `act`, `record_subject`, `record_claim` (or `record: NONE`) |
| storage | two columns on `OperationScenarioSubmission` — the table exists; these are the columns P1 deliberately left out |
| probe | SimForge appends the naming sentence. The Office never writes it. |
| held-out | `author_for_module`'s two templates gain the same sentence — SimForge names its own subjects |
| grading | exact equality on subject **and** claim. No fuzzy matching. |

**What The Office adds:** one block per scenario, on 33 of the 41. It writes no probe text and no
sentence — it names a string.

## The protocol sentence

**Before:**
```
Quote the subject exactly as the request stated it.
```

**After:**
```
When the request names the subject to record under, use that subject exactly, character for
character. Otherwise quote the subject as the request stated it.
```

## What this makes non-comparable

- **`RESPONSE_PROTOCOL_VERSION` 4.0.0 → 5.0.0.** The block changes shape.
- **Every record-rate and subject-rate number in this workstream**, because the probes change too.
  The table in Part 2 is a new baseline, not a continuation of yesterday's.
- The six Greenstone verdicts were already non-comparable from 4.0.0; their status is unchanged.

## What the design does not solve

**It fixes the subject. It does not fix the claim.** `record_claim: "REFUSED AS EMPTY"` is prose, and
exact equality on prose is the same problem one level down. Sorting the split list's 33 records:

| claim kind | count | exact equality? |
|---|---|---|
| a **value** — `143`, `7`, `0`, `2`, `4` | ~9 | yes |
| an **enum** — `false`, `NO`, `WRITTEN`, `UNKNOWN`, `FAILED` | ~10 | yes, if the permitted values are named the way the subject now is |
| **prose** — `NOT RECORDED (2 of 100)`, `REFUSED AS EMPTY`, `±15% of a constant`, `STALE, written <date>` | ~14 | **no** |

Roughly **14 of 33 stay untranscribable** unless the prose claims are rewritten as values or enums.

---

# Part 2 — five models against it

`ALL FOUR` = act **and** record present **and** subject **and** claim, on the same sample.

| shape | | phi4 | llama3.1 | gemma2 | qwen2.5 | mistral |
|---|---|---|---|---|---|---|
| clean positive fact | record · subject | 20 · 20 | 20 · 20 | 20 · 20 | 20 · 20 | 20 · 20 |
| | **all four** | **20** | **19** | **20** | **20** | **20** |
| an absence as the answer | record · subject | 20 · 20 | 19 · 19 | 20 · 20 | 20 · 20 | 20 · 20 |
| | **all four** | **20** | **14** | **20** | **20** | **6** |
| a fact behind a limitation | record · subject | 6 · 6 | 20 · 20 | 10 · 10 | 20 · 20 | 20 · 20 |
| | **all four** | **5** | **0** | **7** | **15** | **20** |
| a refused parameter | record · subject | 2 · 2 | 20 · 20 | 5 · 5 | 20 · 20 | 18 · 18 |
| | **all four** | **0** | **19** | **0** | **0** | **13** |

## 1. The subject channel is solved, completely

**Subject match equals record presence in all twenty cells.** Every model that records at all records
under the named subject, every time. Where the claim is a value, claim match equals subject match
too — `143`, `0` and `7` are 20/20 wherever a record appeared.

**And naming the subject raised presence on the shapes that were failing:**

| | before → after |
|---|---|
| phi4, limitation | 2/20 → 6/20 |
| gemma2, limitation | 2/20 → 10/20 |
| gemma2, refused param | 0/20 → 5/20 |
| qwen2.5, limitation | 13/20 → 20/20 |
| qwen2.5, refused param | 0/20 → **20/20** |
| mistral, refused param | 0/20 → **18/20** |
| llama3.1, refused param | 13/20 → 20/20 |

Not one cell went down. Telling the agent *which* subject to use appears to be what tells it there
is something to record — which is a bigger effect than any wording change measured this week, and it
was not the effect the design was aimed at.

## 2. The act is now the binding channel

The act is graded too, and it is where the joint number falls away:

- *a fact behind a limitation* expects **PROCEED**. **llama3.1 wrote `DECLINE` 18/20** — perfect
  record, zero joint. phi4 5/20, gemma2 7/20, qwen2.5 15/20, mistral 20/20.
- *a refused parameter* expects **DECLINE**. **qwen2.5 wrote `REFUSE` 20/20** and gemma2
  `REFUSE`/`ESCALATE` 20/20 — both 20/20 on the record, **0/20 joint**.
- **mistral wrote `ACT: DECLARE` on 4 of 20** on one shape — an act absent from the four-item menu,
  a protocol violation before any grading question arises.

## 3. Which models can sit an exam whose key is satisfiable

Under the engine as it stands — `_dimension_item` fails a dimension on any FAIL,
`HELD_OUT_PASS_THRESHOLD` is 1.0 and not a knob, ADR-0062 requires three clean attempts — the
per-attempt chance of clearing all four shapes:

| model | per attempt | three attempts |
|---|---|---|
| **mistral** | 0.195 | **0.0074** |
| qwen2.5 | 0 | 0 |
| phi4 | 0 | 0 |
| gemma2 | 0 | 0 |
| llama3.1 | 0 | 0 |

**Four of five models have a channel at exactly 0/20, so their chance is zero, not small.** Only
mistral clears every shape at least once, and its three-attempt figure is 0.7%.

**So: the key is now satisfiable on the record. It is not satisfiable on the act by any model at the
exam's all-or-nothing bar.**

## 4. The thing I have to flag against my own numbers

**The act expectations are my renderings, not Ivan's rulings.**

Ivan ruled the *principles* — `malformed_input` is DECLINE, the split half that no longer escalates
is PROCEED. I wrote the four probes and assigned the expected acts to them. Where a model scores
0/20 on an act, the probe is at least as likely to be the problem as the model.

The clearest case is *a refused parameter*. My probe has **the agent** sending an empty query; the
split-list scenario has **the analyst's request** being unusable. A model reading mine as "a standing
prohibition forbids reporting an empty search as a fact about the market" will `REFUSE` — which is
what qwen2.5 did, 20 times out of 20, and it is a defensible reading of the probe I wrote rather
than a failure to follow the ruling.

So §2 and §3 measure **agreement with my rendering of the key**, and §1 measures the model. Only §1
is a clean result.

---

## What is measured and what is not

| | |
|---|---|
| **measured** | subject match = record presence, 20/20 cells; value claims free once the subject is named; presence rose on every previously-failing cell; act agreement spans 0–100% by model and shape |
| **not measured** | whether the act spread is the models or my probes; anything about prose claims; anything about held-out probes under the naming sentence |
| **not built** | all of it |

No recommendation.
