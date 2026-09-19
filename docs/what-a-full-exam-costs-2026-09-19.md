# What a full exam costs, and what the five dimensions would score

Read-only arithmetic over measured rates. **No battery was started.**

---

## The cost in time, per agent

**Measured on this card**, 17–19 September, phi4 at production settings (0.7 / 4000) with the
Village running: **1.05 s per probe.** (llama3.1:8b measured 3.4 s/probe — smaller and slower.)

A full Unit-A exam for one agent on one module is now **both halves, three attempts each**:

| | probes per attempt | × 3 attempts |
|---|---|---|
| held-out — 1 per never-do entry, +1 per claim prohibition | 5–12 by module | 15–36 |
| **submitted — the split keys** | **5–13 by module** | **15–39** |

Per module, end to end:

| module | held-out | submitted | total probes | **time** |
|---|---|---|---|---|
| `comp_analysis` | 5 | 5 | 30 | **~32 s** |
| `buyer_match` | 6 | 8 | 42 | **~44 s** |
| `assign_contract` | 5 | 8 | 39 | **~41 s** |
| `property_lookup` | 5 | 10 | 45 | **~47 s** |
| `underwrite_deal` | — | 13 | — | **cannot run: no instruction set** |

**An agent certified on all four runnable modules: ~164 probes, about 2 min 52 s.**

The three Greenstone agents across their current modules — Victor on `property_lookup` and
`comp_analysis`, Ronan and Seraphine on `buyer_match` and `assign_contract` — come to **~332
probes, a little over 5 minutes** for the whole venture.

### What that says about ruling 1

**Three attempts is not the expensive part.** Tripling 44 scenarios sounds heavy and costs about
two extra minutes per venture. The ruling holds comfortably; the number that would actually hurt is
the model, and llama3.1 at 3.4 s/probe would make the same sweep **~19 minutes** rather than five.

**And the cost is per attempt, not per scenario**, so the ruling's own fallback is the right one:
if it ever does bite, fewer scenarios or a faster model both scale it down linearly, and dropping
to two attempts would save a third while changing what a pass means.

---

## What the five dimensions would score if one ran today

**Nothing certifies, and the reason is the same for every module.** These are projections from the
measured five-model run, not a battery.

| dimension | fed by | today |
|---|---|---|
| `never_do_adherence` | held-out `never_do_violation` | **PASS**, measured 16/16 on phi4 after the RECORD fix |
| `failure_recognition` | held-out `silent_failure` + submitted `partial_failure` | **FAIL** |
| `sequence_correctness` | submitted `happy_path` | **FAIL** |
| `escalation_discipline` | submitted `escalation_required` | **FAIL** |
| `recovery` | submitted `recovery_after_failure` | **NOT_RUN** on three of four modules |

### Why every submitted dimension fails, and it is one cause

**The Office does not send `situation`.** So every stored key is `puttable == False`, `probe_for`
returns `None`, and `grade_submitted` reports `the_submission_carried_no_situation`. Every
submitted dimension is **NOT_RUN**, not FAIL — nothing was asked.

Which means today's run produces exactly what it produced before this build, and says so more
precisely: `is_competence_unexercised` fires, the row records
`the_competence_half_did_not_run`, and the verdict is **`provisional`**.

**The wiring changes nothing about today's verdict. That is the correct outcome and worth stating
plainly** — the blocker was never the runner.

### And if the situations arrived tomorrow

Then the projections from the five-model run apply, and they are not good:

| | measured on phi4 |
|---|---|
| `happy_path` — a clean fact | act 20/20, subject **9/20** before the subject is named, 20/20 after |
| `partial_failure` — an absence | act 18–20/20, record 18/20 |
| `escalation_required` — as the approved key writes it | **0/200 across five models** |
| `malformed_input` | act 14/20 — and feeds no competence dimension |

`escalation_discipline` would be the one that fails hardest, and **not because the agent is wrong**:
all five models answered the half they could, which is the PROCEED half of the split. That
dimension will only mean something once the split keys are the ones submitted.

**And `_dimension_item` fails a dimension on any FAIL**, with `HELD_OUT_PASS_THRESHOLD` at 1.0 and
three attempts all required. On the numbers above, `sequence_correctness` at 20/20 subject-match is
the only submitted dimension with a plausible path to PASS.

---

## The honest summary

| | |
|---|---|
| time | **not a constraint.** ~5 minutes for the venture, three attempts included |
| the runner | **built and wired**, and changes nothing today |
| what blocks a verdict | `situation` on The Office's payload · an instruction set for `underwrite_deal` · the scheduler switch |
| what blocks a **PASS** after that | the `escalation_required` keys must be the split ones, and `malformed_input`'s act disagreement must be settled |
