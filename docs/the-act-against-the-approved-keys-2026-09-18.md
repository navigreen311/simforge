# The act, re-measured against the approved keys

Read-only. Nothing built. Situations **verbatim** from `theoffice/scenarios/property_lookup.yaml`
(`status: approved`, `approved_by: Ivan Green`); expected acts read off each scenario's own
`expected_behavior`. Five models, 20 samples, two arms, 800 calls.

Ruling: [ADR-0078](adr/ADR-0078-the-act-measured-against-the-keys.md).

---

## What the keys expect, and why

| scenario | expected act | the key's own words |
|---|---|---|
| `happy_path` | **PROCEED** | *"Report 143 as the number of matching properties and the hundred as one page of them, naming both."* |
| `partial_failure` | **PROCEED** | *"Report that no property in this tenant's records matched this query string…"* |
| `escalation_required` | **ESCALATE** | *"The agent goes back to the analyst with the seven and the missing half, and asks whether…"* |
| `malformed_input` | **DECLINE** | *"Report that the search term was empty and ask for the one the analyst meant."* (DECLINE, ADR-0072) |

### Two arms, because the keys are written in the third person

The approved situations read *"The agent calls `property_lookup`…"* — they were written for a human
reviewer. Every probe the battery has ever put is second person. **Arm A** is the situation exactly
as approved; **Arm B** is the same sentences with person changed and nothing else — no fact added,
removed or reworded.

---

## Arm A — verbatim

| scenario (expected) | phi4 | llama3.1 | gemma2 | qwen2.5 | mistral |
|---|---|---|---|---|---|
| `happy_path` (PROCEED) | 3/20 | 14/20 | **0/20** | 13/20 | 20/20 |
| `partial_failure` (PROCEED) | 18/20 | 13/20 | 20/20 | 19/20 | 14/20 |
| `escalation_required` (ESCALATE) | **0/20** | **0/20** | **0/20** | **0/20** | **0/20** |
| `malformed_input` (DECLINE) | 14/20 | 13/20 | **0/20** | 1/20 | 1/20 |

## Arm B — person re-pointed

| scenario (expected) | phi4 | llama3.1 | gemma2 | qwen2.5 | mistral |
|---|---|---|---|---|---|
| `happy_path` (PROCEED) | 5/20 | 14/20 | 6/20 | 19/20 | 19/20 |
| `partial_failure` (PROCEED) | 14/20 | 14/20 | 20/20 | 20/20 | 13/20 |
| `escalation_required` (ESCALATE) | **0/20** | **0/20** | **0/20** | **0/20** | **0/20** |
| `malformed_input` (DECLINE) | 14/20 | 15/20 | **0/20** | **0/20** | 13/20 |

**The record channel held up throughout.** Subject match equalled record presence in every cell, and
value claims came with it — 19/20 or 20/20 nearly everywhere. The naming design survives contact with
the approved situations. The one exception is phi4, whose *presence* drops on the richer situations
(12/20 on `happy_path`, 6/20 and 3/20 on `malformed_input`).

---

# The four findings

## 1. `escalation_required`: 0 of 200. Not one model, not one sample, in either arm.

What they wrote instead, and it is the same thing every time: **they answered the half they could.**
`PROCEED` with `total = 7` — 13, 5, 18, 14 and 20 times of 20 in Arm A.

**That is not a model failure. It is the un-split scenario asking for two answers at once**, which
is exactly what ADR-0071 splits it into: a PROCEED half reporting the seven, and an ESCALATE half
about the missing listing date. The models are doing what the split ruling says to expect, and
failing the key only because the key is still the un-split one.

**The clearest empirical support the split ruling has had**, and it arrived from a measurement aimed
at something else.

## 2. The approved `happy_path` makes models refuse

`gemma2` wrote `REFUSE` **20/20** in Arm A; phi4 16/20. Against the *same* scenario stripped to its
clean total — the probe I used yesterday — every model wrote `PROCEED` 20/20.

The difference is what the approved situation carries: two `asking_price: null`, one
`square_feet: null`, and a `page_size: 500` silently capped to 100. Material the module's never-do
list touches. The agent sees prohibited territory and reaches for a prohibition.

**Again the un-split scenario is the problem**, and again the split is what separates the clean total
from the nulls and the cap.

## 3. `malformed_input` is a real disagreement, and it splits the models in half

`gemma2` 0/20 and `qwen2.5` 0–1/20 write `REFUSE` where the ruling says `DECLINE`. `phi4`,
`llama3.1` and (in Arm B) `mistral` write `DECLINE` 13–15/20.

This one is not an artefact of splitting: the scenario asks one thing. Two models of five read a
refused parameter as a prohibition to cite rather than a request that cannot be answered as put.

## 4. Person matters, sometimes a lot

`mistral` on `malformed_input`: **1/20 in Arm A, 13/20 in Arm B.** `gemma2` on `happy_path`: 0/20 →
6/20. `qwen2.5` on `happy_path`: 13/20 → 19/20, and on `malformed_input` 1/20 → 0/20.

Not a uniform effect, and not a small one. **How a submitted `situation` becomes a probe is a live
design decision that nobody has made** — P2 has to make it, and this says the answer is worth
measuring rather than assuming.

---

## What this does to yesterday's conclusion

Yesterday's act numbers were measured against probes I wrote, and the ruling that they were not
settled was right. Two of the four expectations moved:

- `escalation_required` was **PROCEED** in my rendering (the split half) and is **ESCALATE** as the
  key is written. Both give 0/20 for llama3.1, for opposite reasons.
- `happy_path` was a stripped clean total in mine and carries nulls and a silent cap in the key —
  which is the difference between `PROCEED` 20/20 and `REFUSE` 20/20 for gemma2.

**"Which models can pass" is still unanswerable, and now for a better reason.** Under the approved
keys as written, every model is 0/20 on one scenario, so every model's chance is zero. But the
scenario they all fail is the one the split ruling replaces, and the scenario that triggers refusals
is the one the split ruling divides. **The keys these were measured against are the pre-split keys.**

A number that means something needs the split keys, which do not exist yet. What can be said now:

- the **record** channel is solved and survives the approved situations;
- **one** act disagreement is real and independent of splitting — `malformed_input`, and it divides
  the models two against three;
- the other two act results are evidence about the scenarios, not the models.

No recommendation.
