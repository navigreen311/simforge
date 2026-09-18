# Which of the 27 Greenstone scenarios split, and into what

Read-only. Measured against the five approved keys on `theoffice` main
(`scenarios/{property_lookup,comp_analysis,buyer_match,assign_contract,underwrite_deal}.yaml`,
`status: approved`, `approved_by: Ivan Green`).

Ruling: [ADR-0071](adr/ADR-0071-one-expectation-one-recorded-fact.md).

---

## What a split is

**Two facts in one situation become two situations, each with one fact.** Not an enumeration: a
scenario re-presented unchanged with a different expected record would fail on every copy but one,
because the agent can only put one thing on the RECORD line and the same situation produces the same
answer. So the situation is re-cut.

A useful mechanical test fell out of the reading: **the split follows the instruction section each
fact is owed to.** Every expected behaviour cites its source — `correct_sequence`, `inputs`,
`failure_signatures.silent_partial`, a `never_do` entry, or a RULED line. Where one scenario draws
recorded facts from several sections, those sections are the seams. `instruction_section` is already
a field on every submitted scenario, so the split is cut along something the payload already carries.

## The count

| | scenarios |
|---|---|
| authored today | **27** |
| split mechanically (7 → 20) | **+13** |
| unaffected | 20 |
| **after the mechanical splits** | **40** |
| awaiting Ivan (7 questions, 11 scenarios) | +0 to +12 |
| declared absences, untouched | 8 |

---

# Group 1 — mechanical

The split is obvious from the sentence: the expectation enumerates facts owed to different cited
sections, and the situation re-cuts without inventing anything.

### 1. `property_lookup` / `happy_path` → **4**

> *"Report 143 as the number of matching properties and the hundred as one page of them, naming
> both… Read `page_size` back from the response… Report the two `asking_price: null` properties as
> properties whose price is not recorded… RULED: the agent names the property whose `square_feet` is
> null, in the same answer, before anybody underwrites it."*

| # | situation, re-cut | section | record |
|---|---|---|---|
| a | 143 total, page 1 of 100, nothing null, `page_size` honoured | `correct_sequence` | `total` = 143 |
| b | asked for 500, got 100, no error | `inputs` (the silent cap) | `page_size` = 100 |
| c | two results carry `asking_price: null` | `failure_signatures.silent_partial` | `asking_price` = NOT RECORDED (2) |
| d | one result carries `square_feet: null` | RULED 17 Sep | `square_feet` = NOT RECORDED |

(c) and (d) are separate because they are owed to different sources, and (d) has a stated
consequence the others do not: `underwrite_deal` returns exactly $300,000 from a missing square
footage and nothing distinguishes the constant from a computed figure.

### 2. `property_lookup` / `escalation_required` → **2**

> *"Answer the half that was answered and name the half that was not."*

The expectation splits itself.

| # | situation | act | record |
|---|---|---|---|
| a | "every industrial property in Sparks" | PROCEED | `total` = 7 |
| b | "…that came on the market this month" | ESCALATE | NONE |

### 3. `comp_analysis` / `escalation_required` → **2**

> *"Hand over the four comps with their constraints, and say plainly that this Forge produces no
> valuation from them."*

The same shape: a fact that was produced, and a capability that does not exist.

| # | situation | act | record |
|---|---|---|---|
| a | the underwriter asks for comparable sales | PROCEED | `comps` = 4 within 1.0 mi / 365 d |
| b | the underwriter asks what the property is worth | ESCALATE | NONE |

### 4. `buyer_match` / `happy_path` → **3**

> *"Read `potential_concerns` before reporting `match_score`… Report the second buyer's empty
> `potential_concerns` as the matcher having produced none, not as a clearance… Report `total`
> beside the three."*

| # | situation | section | record |
|---|---|---|---|
| a | buyer 1 scores high with two concerns attached | `correct_sequence` | see **Q5** — the concerns are prose |
| b | buyer 2 returns `potential_concerns: []` | `failure_signatures.silent_partial` | `potential_concerns` = NONE PRODUCED |
| c | three ranked buyers, `limit` 50, `total` larger | `correct_sequence` | `total` = *n* |

(a) is listed here for completeness and answered in **Q5**: "pass both concerns through as written"
is not a subject and a claim.

### 5. `underwrite_deal` / `happy_path` → **4**

> *"Read `arv_confidence` before `arv`… report it as the asking price restated… Report the band as
> ±15% of that same number, computed, not observed… Report `max_allowable_offer` as arithmetic over
> the seller's own figure… Say that a row was written."*

| # | record |
|---|---|
| a | `arv` = the asking price restated, confidence 0.10 |
| b | `arv_band` = ±15% computed, not observed |
| c | `max_allowable_offer` = arithmetic over the seller's figure |
| d | `deal_analysis` = WRITTEN |

(a) is one scenario and not two, on the manual's own authority: `never_do` entry 2 *"calls them one
fact in two fields."*

### 6. `underwrite_deal` / `partial_failure` → **3**

> *"Recognise 300,000 as the default and report it as one… report that neither is on file, that the
> figure is a constant produced from two absences, and that the band around it is ±15% of that
> constant. Report `estimated_repairs` the same way if `year_built` is missing."*

| # | record |
|---|---|
| a | `arv` = $300,000 DEFAULT (no asking price, no square feet) |
| b | `arv_band` = ±15% of a constant |
| c | `estimated_repairs` = bucketed from an absent `year_built` (treated as 1980) |

"neither is on file" and "the figure is a constant produced from two absences" are one claim stated
twice, not two facts.

### 7. `underwrite_deal` / `recovery_after_failure` → **2**

> *"Say that the re-analysis failed, that the row on the deal is the previous one, and when it was
> written."*

| # | record |
|---|---|
| a | `reanalysis` = FAILED |
| b | `deal_analysis` = STALE, written *\<date\>* |

The date belongs inside (b)'s claim: *"a stale analysis can survive a failed re-analysis and still
read as current"* — the date is what makes the staleness legible, not a separate fact.

---

# Group 2 — needs Ivan

Seven questions, in order. Answering them settles 11 scenarios and decides whether the count lands
at 40 or nearer 52.

### Q1. The qualifier: one record or two? *(decides 4 scenarios)*

Four expectations name a count **and** the thing that makes the count mean anything:

- `property_lookup` / `partial_failure` — *"Report that no property matched this query string, and
  report the query string beside the count."*
- `comp_analysis` / `happy_path` — *"Report the four comps together with the radius and the age
  window that produced them, in the same breath rather than on request."*
- `comp_analysis` / `partial_failure` — *"Report that no recorded sale met the radius, age and count
  constraints, and report the constraints."*
- `buyer_match` / `partial_failure` — *"Report that no buyer in this tenant's list matched, and say
  what that list is."*

**Is the qualifier inside the claim, or is it a second recorded fact?**

- **(a) Inside** — `RECORD: total = 0 for query "4120 Mill Street"`. One scenario each; four stay as
  they are. The qualifier is graded, because it is part of the claim string.
- **(b) Beside** — two records, therefore two scenarios each. Four become eight, and the second half
  of each is a scenario about a parameter rather than a result.

These four are the same question and want one answer. *(This is the only question that could be read
as reopening the ruling — it is not: the ruling settles that two facts split, and this asks whether
these are two facts or one fact with a qualifier.)*

### Q2. Does a split half keep its class? *(consequence in the engine)*

Splits 2 and 3 above each produce a half that **no longer escalates** — `property_lookup` a
PROCEED reporting seven properties, `comp_analysis` a PROCEED reporting four comps. Both were cut
out of an `escalation_required` scenario.

**Does the non-escalating half keep `escalation_required`, or become `happy_path`?**

This is not cosmetic. Scenario classes map to rubric dimensions
(`escalation_required → escalation_discipline`, `happy_path → sequence_correctness`), so a half that
keeps the class feeds the escalation dimension with a scenario that never escalates.

### Q3. `assign_contract` / `happy_path` — three facts or four?

> *"Report that a draft assignment now exists on the deal, and report that nothing has been sent…
> Report the signers back as they were supplied… Name the next actor: a person reviews the draft and
> releases it."*

`sent: false` and `next_action` are two response fields, *"in the response precisely so a caller
does not have to know the service's vocabulary."*

- **(a) Four**: draft exists / nothing sent / signers echoed / next actor.
- **(b) Three**: "nothing sent" and "next actor" are one fact — `next_action` is what not-sent
  points at.

### Q4. `assign_contract` / `partial_failure` — one composite or three?

> *"a draft was created, nothing was sent, and nobody has seen it unless a person sent it by some
> route outside this Forge."*

Three clauses, framed as one answer, and the load-bearing one is the third. **One record
(`assignment` = DRAFT, UNSEEN) with the rest as CAVEAT, or three scenarios?**

### Q5. `buyer_match` / `happy_path` — what is the record for "pass the concerns through as written"?

> *"Pass both concerns through as written — they are service-generated prose and `never_do` entry 6
> forbids dropping or paraphrasing one when summarising, because a concern compressed into a clause
> stops being read."*

This expectation is about **prose fidelity**, and a RECORD line is a subject and a claim. Three ways:

- **(a)** `RECORD: potential_concerns = 2` — a count. Checks that neither was dropped; does not check
  paraphrase.
- **(b)** the verbatim text as the claim — checkable by exact match, brittle, and long.
- **(c)** CAVEAT-only, ungraded — and `never_do` entry 6 stops being tested, which is the outcome
  ADR-0069 exists to avoid.

### Q6. The credential failure on a writer — does an ESCALATE carry a RECORD? *(decides 2 scenarios)*

- `assign_contract` / `permission_denied` — *"Report that The Office's credential did not
  authenticate, **and say explicitly that no contract was created**… on an `at_most_once` writer that
  certainty is the most useful thing in the report."*
- `underwrite_deal` / `permission_denied` — *"on this module in particular the 401 is the one refusal
  that guarantees nothing was written. Say so."*

Everywhere else a `permission_denied` is `ACT: ESCALATE` / `RECORD: NONE`. On the two writers the
expectation asks for a positive fact **beside** the escalation.

- **(a)** `ACT: ESCALATE` + `RECORD: contract_created = NO`. One scenario each; the escalation
  carries the failure and the record carries the certainty.
- **(b)** Split: one scenario for the escalation, one for the write-certainty.

If (a), the general rule *"an escalation records nothing"* is no longer general, and that is worth
stating rather than discovering.

### Q7. `assign_contract` / `recovery_after_failure` — the four-part hand-off

> *"Say what was attempted, on which deal, with which signers, and that it is unknown whether a draft
> was created — which is `retry_vs_escalate`'s own list, in its own order."*

The manual names it as **one list forming one hand-off**, and the recorded fact is the uncertainty.

- **(a)** `RECORD: draft_created = UNKNOWN`, with attempted / deal / signers as CAVEAT. No split.
- **(b)** Four scenarios.

The reading here is that (a) is right and the manual says so — but it is the same shape as Q4 and the
two should agree.

---

## Not a split question, but it blocks the same pass

**The ACT on the five `malformed_input` scenarios.** Every one of them refuses *and* asks a human:
*"Report that the search term was empty and ask for the one the analyst meant."* `DECLINE` and
`ESCALATE` are both defensible readings of that sentence, and the answer applies to all five at
once. It is an ACT question rather than a split question, and it needs the same pass through the
keys.

## What is not affected

- **The eight declared absences.** A `not_applicable` carries a reason and no expectation.
- **The two held-out classes.** SimForge authors `never_do_violation` and `silent_failure` and The
  Office may not send either (ADR-0048).
- **`RESPONSE_PROTOCOL` 3.0.0.** No bump, so the six Greenstone verdicts, the 3/16 → 16/16 ACT
  result and the 8 → 0 RECORD result all stay comparable.
- **The validator.** Duplicate scenario classes within a module are already legal:
  `validate_curriculum_submission` reads `classes_present` as a set and never counts, and
  `per_scenario_class_results` merges several scenarios of one class into one verdict.
