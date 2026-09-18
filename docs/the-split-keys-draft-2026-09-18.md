# The split keys — what was written, what changed, what needs Ivan

`docs/split-keys-draft/*.yaml` — five files, **41 scenarios, every one marked `status: draft`.**
Rulings: [ADR-0079](adr/ADR-0079-the-split-keys-are-drafted.md) and
[ADR-0080](adr/ADR-0080-the-band-is-withdrawn-the-rest-pair.md).

> **REVISED TWICE, 18 September 2026.** ADR-0080 withdrew two scenarios and added two (41).
> ADR-0081 added two more — the `estimated_repairs_basis` counterpart and the pre-call REFUSE
> case — for **43**. The table below is current.

---

## Where they are, and why not in `theoffice`

These are The Office's content and belong in `theoffice/scenarios/`. They are staged here for one
reason, stated so it can be overruled in a sentence:

**`theoffice`'s working tree has 65 uncommitted files, and the five approved keys are among them** —
`A scenarios/property_lookup.yaml` and the other four are staged and not committed, alongside
in-flight work on the broker, two migrations and `docs/decisions.md`. Committing into that tree
risks entangling with work in progress that is not mine.

Moving five YAML files across once that work lands is a minute's work. Nothing here depends on the
location.

---

## The count

| module | before | after | classes |
|---|---|---|---|
| `property_lookup` | 5 | **9** | 2 happy_path · 4 partial_failure · 1 each malformed / permission / escalation |
| `comp_analysis` | 5 | **5** | 1 · 1 · 1 · 1 · 1 |
| `buyer_match` | 5 | **8** | 2 happy_path · 2 partial_failure · **2 malformed_input** · 1 · 1 |
| `assign_contract` | 6 | **8** | 3 happy_path · 1 partial · 1 malformed · 1 permission · 1 escalation · 1 recovery |
| `underwrite_deal` | 6 | **13** | 4 happy_path · 3 partial · **2 malformed_input** · 1 permission · 1 escalation · 2 recovery |
| | **27** | **41** | |

**35 expect a record, 8 expect `RECORD: NONE`, 22 carry `record_claim_options`.**
**12 scenarios still carry a `NEEDS IVAN` note**, down from 20 at the first draft — and every
remaining one is about the **claim** or the **class**, none about a situation, an act or a subject.

## A correction to my own arithmetic

The F1 document said `property_lookup` becomes **"3 `happy_path` / 3 `partial_failure`"**. It is
**2 / 4**. My table listed three `partial_failure` and silently dropped the module's *original*
`partial_failure` (`total = 0`), padding `happy_path` with an em-dash. The module total was right at
9 either way, and **the ruling is unaffected** — you ruled *re-class ⓑ ⓒ ⓓ, and what it tests wins*,
which is unambiguous. "3/3" was my label, not your decision.

---

## What changed in the situations, and the two changes are different

**The split** narrows each situation to the one fact its scenario grades. Facts *are* removed from a
variant — that is what a split is (ADR-0071: two facts in one situation become two situations).
Nothing is added and nothing is reworded.

**The person** rewrite: every situation is now second person, addressed to the agent. The approved
keys are third person (*"The agent calls `property_lookup`…"*) because they were written for a human
reviewer.

**Confirmed: the person rewrite adds no fact, removes no fact and rewords none.** It changes
`The agent calls` → `You call`, `It receives` → `You receive`, `the agent holds` → `you hold`, and
nothing else. Every number, status code, field name, quoted `detail` string and clause survives
verbatim.

That this matters is measured, not assumed: **`mistral` on `malformed_input` went 1/20 → 13/20 on
the expected act between the verbatim and re-pointed arms** (ADR-0078). How a `situation` becomes a
probe is a real decision, and this draft makes it.

`expected_behavior` and `expected_escalation` are the approved key's own sentences, trimmed to the
fact each scenario grades. Trimming is the split; no sentence is rewritten.

---

## Flagged — 20 scenarios carry a `draft_note`, and these are the ones that need judgment

### The claim is prose and exact equality cannot grade it (9)

`property_lookup` ⓒ ⓓ and the `total = 0` qualifier · `comp_analysis` happy_path and partial_failure
(the constraints) · `buyer_match` partial_failure · the two `malformed_input` refusal strings.

Each names the enum or count that would make it gradable. **None is applied** — the claim-channel
proposal is proposed, not ruled.

### Q1 pulls against transcription (4)

`total = 0 for query "4120 Mill Street"` · `comps = 4 within 1.0 mi / 365 days` and its zero ·
`matched_buyers = 0 of this tenant's buyer list`.

You ruled a count and its qualifier are **one fact**, so they are single scenarios. That makes the
claim prose. Grading the bare count would drop the qualifier — which is what Q1 refused.

### The act contradicts the key's own ruling (1) — the sharpest one

**`underwrite_deal / partial_failure`.** The approved `expected_escalation` carries
*"RULED 17 September 2026: REFUSE. The agent does not call this module for a property with neither
an asking price nor a square footage."* But the situation has the agent **already holding the
`200`.**

Either the situation predates the ruling and should be rewritten so no call has been made — which
makes the act `REFUSE` and this a different scenario — or the ruling governs the *next* call and
this scenario grades the reporting of a result already in hand. **Not guessed.**

### A scenario with two possible responses (1)

`buyer_match / malformed_input` says *"a `422` … — or, if the property id happens to be a
well-formed UUID, a `404`."* One scenario cannot have two expected answers. The draft takes the 404
branch; splitting it would make the module 8.

### Options of my construction (3)

`signers = AS SUPPLIED, UNVERIFIED` — the alternative `VERIFIED` describes a state this Forge cannot
reach, and an option nothing can produce is a distractor rather than a choice.
`estimated_repairs` and `buyer_match`'s concern count are similar.

### A subject renamed against a ruling (1)

Q7 said `draft_created = UNKNOWN`. The draft writes `contract_created` so that all four
write-certainty scenarios on `assign_contract` share one subject — a subject varying per scenario is
a second thing for the agent to get right. **Flagged rather than silently changed.**

### And one structural leak worth reading

`buyer_match` ⓑ. If `record_claim_options` differs per probe, **the option list itself says which
scenario is being put.** The draft gives the two concern scenarios an identical option set for that
reason. The same constraint will bite everywhere options are used, and it is the same shape as the
naming sentence's leak: anything that varies with the expected answer is a signal.

---

## What is not in the draft

- **The naming sentences.** `record_subject` and `record_claim_options` are *fields*; SimForge
  renders them into the probe (ADR-0077). The keys do not carry probe text.
- **The five ungradable claims**, left as prose with their notes:
  [the-five-ungradable-claims.md](the-five-ungradable-claims-2026-09-18.md).
- **Approval.** Every file says `status: draft`. They are not submittable until Ivan reviews them,
  which is the convention `theoffice` already runs on.
