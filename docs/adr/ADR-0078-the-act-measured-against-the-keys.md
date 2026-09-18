# ADR-0078 — The act, measured against the keys

**Status:** accepted · **Decided by:** Ivan Green, 18 September 2026 · **Nothing built.**
**Follows:** [ADR-0077](ADR-0077-the-scenario-names-the-subject.md), whose act numbers this
supersedes.

---

## The ruling

**The act measurement is not settled. Those probes carry Claude's rendering of the expected act, not
Ivan's scenarios. Before any conclusion about which models can pass, re-measure against probes drawn
from the approved Greenstone keys.**

---

## The ruling was right, and two of four expectations moved

Situations **verbatim** from `theoffice/scenarios/property_lookup.yaml` (`status: approved`), acts
read off each scenario's own `expected_behavior`. Five models, 20 samples, two arms — the approved
situations are third person, every probe the battery puts is second person, so the person was varied
as a control. 800 calls.

- `escalation_required` was **PROCEED** in my rendering (I had used the *split half*) and is
  **ESCALATE** as the key is written.
- `happy_path` was a stripped clean total in mine, and in the key carries two `asking_price: null`,
  one `square_feet: null`, and a `page_size: 500` silently capped to 100.

Full tables: [the-act-against-the-approved-keys.md](../the-act-against-the-approved-keys-2026-09-18.md).

## The four findings

### 1. `escalation_required`: 0 of 200

Not one model, not one sample, in either arm, wrote `ESCALATE`. What they wrote instead was the same
every time: **`PROCEED` with `total = 7` — they answered the half they could**, 13, 5, 18, 14 and 20
times of 20.

**That is not a model failure. It is the un-split scenario asking for two answers at once**, which is
precisely what ADR-0071 splits into a PROCEED half and an ESCALATE half. The models are doing what
the split ruling says to expect and failing the key only because the key is still the un-split one.

The strongest empirical support the split ruling has had, and it came from a measurement aimed at
something else.

### 2. The approved `happy_path` makes models refuse

`gemma2` wrote `REFUSE` **20/20** verbatim; phi4 16/20. The same scenario stripped to its clean
total got `PROCEED` 20/20 from every model yesterday. The difference is the nulls and the silent
cap — material the module's never-do list touches, so the agent reaches for a prohibition.

**The un-split scenario again**, and the split is what separates the clean total from the nulls and
the cap.

### 3. `malformed_input` is a real disagreement

`gemma2` 0/20 and `qwen2.5` 0–1/20 write `REFUSE` where the ruling says `DECLINE`; `phi4`,
`llama3.1` and `mistral` (re-pointed) write `DECLINE` 13–15/20. **This one is not an artefact of
splitting** — the scenario asks one thing, and two models of five read a refused parameter as a
prohibition to cite rather than a request that cannot be answered as put.

### 4. Person matters, sometimes a lot

`mistral` on `malformed_input`: **1/20 verbatim, 13/20 re-pointed.** `gemma2` on `happy_path`: 0/20 →
6/20.

**How a submitted `situation` becomes a probe is a live design decision nobody has made.** P2 has to
make it, and this says the answer should be measured rather than assumed.

### And the record channel held

Subject match equalled record presence in every cell, and value claims came with it, 19–20/20 almost
everywhere. **The naming design survives contact with the approved situations.** The exception is
phi4, whose presence falls on the richer ones.

## What can and cannot be concluded

**"Which models can pass" remains unanswerable, and now for a better reason.** Every model is 0/20
on one scenario, so every chance is zero — but that scenario is the one the split replaces, and the
scenario that triggers refusals is the one the split divides. **These were measured against the
pre-split keys.**

What stands:

- the **record** channel is solved and survives the approved situations;
- **one** act disagreement is real and independent of splitting — `malformed_input`, dividing the
  models two against three;
- the other two act results are evidence about the **scenarios**, not the models.

A number that means something needs the split keys, and they do not exist yet.

## The claim channel, proposed alongside

Naming the permitted claim values, in the same shape as the subject:
[the-claim-channel.md](../the-claim-channel-2026-09-18.md).

It reaches **23 of 33 records without a judgment call**, 28 if Q1 is reopened, and stops at 28. The
last five are the scenarios about *how a figure was produced* — `±15% of a constant`, `the asking
price restated` — which have no value that carries them, and which are the most important thing
`underwrite_deal` has to say.

No recommendation.
