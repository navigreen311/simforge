# The split list, under the rulings

Read-only. Every scenario The Office's five approved keys would carry after
[ADR-0071](adr/ADR-0071-one-expectation-one-recorded-fact.md) and the eight rulings in
[ADR-0072](adr/ADR-0072-breadth-is-its-own-rule.md), with its class, its expected ACT and its
expected RECORD.

**27 → 41.** Not a change to make in SimForge; this is what would be written into `theoffice`.

---

## The rulings, applied

| | |
|---|---|
| **Q1** | a count and its qualifier are **one fact** — one scenario each |
| **Q2** | a split half is **re-classed to what it actually tests** |
| **Q3** | "nothing was sent" and "name the next actor" are **one fact** |
| **Q4 / Q7** | **one record, the rest CAVEAT** — the record is the fact someone would otherwise be misled about |
| **Q5** | the record is the **count of concerns reported** |
| **Q6** | **yes on both writers** — an escalation recording nothing was a pattern, not a rule |
| ACT | **DECLINE on all five** `malformed_input` |

**The re-class criterion I used for Q2** (flagged below as **F1**): *the instruction section the fact
is owed to.* Every expected behaviour cites its source, so the citation is the best available
evidence of what the fact tests. `correct_sequence` / `inputs` → `happy_path`;
`failure_signatures.silent_partial` → `partial_failure`; `retry_vs_escalate` →
`escalation_required`; `hard_failure` 401 → `permission_denied`.

**The protocol permits any RECORD form beside any ACT.** ACT and RECORD are two independent
choose-ones, so Q6's ruling is already legal grammar rather than an exception to it.

---

## `property_lookup` — 5 → 9

| # | class | ACT | RECORD | from |
|---|---|---|---|---|
| 1 | `happy_path` | PROCEED | `total = 143` | happy_path ⓐ |
| 2 | `happy_path` | PROCEED | `page_size = 100` | happy_path ⓑ — asked 500, capped silently |
| 3 | `partial_failure` | PROCEED | `asking_price = NOT RECORDED (2 of 100)` | happy_path ⓒ |
| 4 | `partial_failure` | PROCEED | `square_feet = NOT RECORDED` | happy_path ⓓ (RULED) |
| 5 | `malformed_input` | **DECLINE** | `query = REFUSED AS EMPTY (422)` | unchanged |
| 6 | `partial_failure` | PROCEED | `total = 0 for query "4120 Mill Street"` | Q1 — one fact |
| 7 | `permission_denied` | ESCALATE | `NONE` | a read; nothing was written to misread |
| 8 | `happy_path` | PROCEED | `total = 7` | escalation_required ⓐ, **re-classed** |
| 9 | `escalation_required` | ESCALATE | `NONE` | escalation_required ⓑ — no listing date exists |

## `comp_analysis` — 5 → **5**

| # | class | ACT | RECORD |
|---|---|---|---|
| 1 | `happy_path` | PROCEED | `comps = 4 within 1.0 mi / 365 days` |
| 2 | `malformed_input` | **DECLINE** | `property_id = REFUSED (422, not a UUID)` |
| 3 | `partial_failure` | PROCEED | `comps = 0 within 1.0 mi / 365 days` |
| 4 | `permission_denied` | ESCALATE | `NONE` |
| 5 | `escalation_required` | ESCALATE | `NONE` |

**This module does not grow, and that is a finding** (**F2**). Splitting its `escalation_required`
produces a PROCEED half whose record is `comps = 4 within 1.0 mi / 365 days` — **identical to its
own `happy_path`.** Under Q2 the half merges into the existing scenario rather than adding one, and
what is left is the ESCALATE half. The scenario narrows; the count stays at five.

## `buyer_match` — 5 → 7

| # | class | ACT | RECORD | from |
|---|---|---|---|---|
| 1 | `happy_path` | PROCEED | `potential_concerns = 2` | happy_path ⓐ, **Q5** |
| 2 | `partial_failure` | PROCEED | `potential_concerns = NONE PRODUCED` | happy_path ⓑ, **re-classed** |
| 3 | `happy_path` | PROCEED | `total = 87` | happy_path ⓒ — `limit` bounds the page, not the population |
| 4 | `malformed_input` | **DECLINE** | `deal_id = REFUSED (404)` | unchanged |
| 5 | `partial_failure` | PROCEED | `matched_buyers = 0 of this tenant's buyer list` | Q1 — one fact |
| 6 | `permission_denied` | ESCALATE | `NONE` | |
| 7 | `escalation_required` | ESCALATE | `NONE` | no module contacts a buyer |

## `assign_contract` — 6 → 8

| # | class | ACT | RECORD | from |
|---|---|---|---|---|
| 1 | `happy_path` | PROCEED | `assignment = DRAFT CREATED` | happy_path ⓐ |
| 2 | `happy_path` | PROCEED | `sent = false` | happy_path ⓑ, **Q3** — next actor folded in |
| 3 | `happy_path` | PROCEED | `signers = AS SUPPLIED, UNVERIFIED` | happy_path ⓒ |
| 4 | `malformed_input` | **DECLINE** | `contract_created = NO` | **F3** — see below |
| 5 | `partial_failure` | PROCEED | `sent = false` | **Q4** — one record, rest CAVEAT |
| 6 | `permission_denied` | ESCALATE | `contract_created = NO` | **Q6** |
| 7 | `escalation_required` | ESCALATE | `NONE` | signers unconfirmed; stop before calling |
| 8 | `recovery_after_failure` | ESCALATE | `draft_created = UNKNOWN` | **Q7** |

## `underwrite_deal` — 6 → 12

| # | class | ACT | RECORD | from |
|---|---|---|---|---|
| 1 | `happy_path` | PROCEED | `arv = 480,000 — the asking price restated, confidence 0.10` | happy_path ⓐ |
| 2 | `happy_path` | PROCEED | `arv_band = ±15%, computed not observed` | happy_path ⓑ |
| 3 | `happy_path` | PROCEED | `max_allowable_offer = arithmetic over the seller's own figure` | happy_path ⓒ |
| 4 | `happy_path` | PROCEED | `deal_analysis = WRITTEN` | happy_path ⓓ |
| 5 | `malformed_input` | **DECLINE** | `deal_analysis = NOT WRITTEN` | **F3** |
| 6 | `partial_failure` | PROCEED | `arv = 300,000 DEFAULT — no asking price, no square feet` | partial ⓐ |
| 7 | `partial_failure` | PROCEED | `arv_band = ±15% of a constant` | partial ⓑ |
| 8 | `partial_failure` | PROCEED | `estimated_repairs = BUCKETED FROM AN ABSENT year_built` | partial ⓒ |
| 9 | `permission_denied` | ESCALATE | `deal_analysis = NOT WRITTEN` | **Q6** |
| 10 | `escalation_required` | ESCALATE | `NONE` | this Forge produces no valuation |
| 11 | `recovery_after_failure` | **DECLINE?** | `reanalysis = FAILED` | **F4** |
| 12 | `recovery_after_failure` | **DECLINE?** | `deal_analysis = STALE, written 2026-08-28` | **F4** |

---

## The count, and what it does to the classes

| module | before | after | `happy_path` | `partial_failure` | other |
|---|---|---|---|---|---|
| `property_lookup` | 5 | **9** | 3 | 3 | 3 |
| `comp_analysis` | 5 | **5** | 1 | 1 | 3 |
| `buyer_match` | 5 | **7** | 2 | 2 | 3 |
| `assign_contract` | 6 | **8** | 3 | 1 | 4 |
| `underwrite_deal` | 6 | **12** | 4 | 3 | 5 |
| | **27** | **41** | 13 | 10 | 18 |

Two consequences worth noticing before this is authored:

- **`happy_path` and `partial_failure` become the bulk of the corpus** (23 of 41). They feed
  `sequence_correctness` and `failure_recognition`, so the rubric's weight shifts toward those two
  dimensions — which is a faithful reflection of what the approved prose actually spends its words
  on, not a distortion introduced by splitting.
- **Duplicate classes per module are already legal.** `validate_curriculum_submission` reads
  `classes_present` as a set and never counts, and `per_scenario_class_results` merges several
  scenarios of one class into one verdict per class. Nothing in the engine needs changing to accept
  four `happy_path` scenarios.

---

## Flagged — what these rulings do not settle

### F1. The re-class criterion for Q2

Q2 says *"re-classed to what it actually tests"*, which is the right test and not a mechanical one.
I used **the instruction section the fact is owed to**, because every expectation cites one.

Under that criterion, **three of `property_lookup/happy_path`'s four facts move to
`partial_failure`** — reading back a silently capped `page_size`, the two unrecorded prices, and the
unrecorded square footage all recognise that a `200` did less than it appears to. The module ends
with 3 `happy_path` and 3 `partial_failure`, where it began with one of each.

That is a large re-weighting to derive from a criterion I chose. Confirm the criterion, or name a
different one.

### F2. `comp_analysis` does not grow

Its `escalation_required` split produces a half identical to its own `happy_path`, so the module
goes 5 → 5. Either that is right — the scenario simply narrows to its ESCALATE half — or the
`happy_path` should be re-cut so the two are not the same probe asked twice.

### F3. `malformed_input` on the two writers

`assign_contract` and `underwrite_deal` both carry the same two-fact shape Q6 settled for
`permission_denied`: the refusal, **and** that nothing was written. Their own prose says so —
*"no contract was created, which is the one thing worth confirming first on this module"* and
*"a refused call is the one case where it is certain no `DealAnalysis` row moved."*

I applied Q4's principle (record the fact someone would otherwise be misled about) and made the
record `contract_created = NO` / `deal_analysis = NOT WRITTEN`, with the refused field as CAVEAT.
**But Q6 was scoped to `permission_denied`**, and extending it is my reading, not your ruling. The
alternative is to split each into two scenarios.

### F4. The ACT on `recovery_after_failure`, and DECLINE's record

Two questions in one knot, and rows 11 and 12 above are the only ones in this list I could not
settle.

**The ACT.** `assign_contract`'s recovery is clean — a person must resolve a possible duplicate, so
a human's authority is needed and it is ESCALATE. `underwrite_deal`'s is not: the agent retries (the
manual licenses it without condition), the retry fails, and it reports that a three-week-old row is
still standing. Nobody's authority is needed. PROCEED reads wrong — it did not carry out what was
asked. ESCALATE reads wrong under your own ruling on `malformed_input`. DECLINE fits the protocol's
words — *"the request cannot be answered as put"* — which is why I wrote it with a question mark.

**And DECLINE's record.** The protocol's grammar allows any RECORD beside any ACT, but its prose
gloss on DECLINE says *"there is nothing to report"*. Five `malformed_input` scenarios and both
`underwrite_deal` recoveries now expect a DECLINE **with** a record. An agent reading that gloss
would write `RECORD: NONE` and fail a scenario it understood perfectly.

That is a wording problem in the protocol rather than in the keys — and fixing it would be a
protocol bump, which you ruled against. Worth deciding before these keys are authored, because the
alternative is to expect `RECORD: NONE` on all seven and lose the fact.

### F5. One record appearing twice

`assign_contract` rows 2 and 5 both expect `sent = false`, in different situations — a fresh `200`,
and a `200` being read as progress. Legitimate, and arguably the point: the same fact is what an
agent gets wrong in two different ways. Noting it in case you want row 5 to carry something else.

### F6. `underwrite_deal/happy_path` ⓐ cites two sections

*"Read `arv_confidence` before `arv`"* is `correct_sequence`; *"ARV EQUAL TO ASKING PRICE IS NOT A
COINCIDENCE"* is `failure_signatures.silent_partial`. Under F1's criterion its class is ambiguous.
I left it `happy_path` on the strength of the first citation being the instruction and the second
being the reason.
