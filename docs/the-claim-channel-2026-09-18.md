# The claim channel — naming the permitted values

Read-only. Nothing built. A proposal in the same shape as the named subject
([ADR-0077](adr/ADR-0077-the-scenario-names-the-subject.md)), plus what it cannot reach.

---

## The proposal

The scenario names the permitted claim values; the agent picks one; grading stays **exact equality**.

```yaml
expected_answer:
  act: PROCEED
  record_subject: sent
  record_claim: "false"
  record_claim_options: ["true", "false"]     # named to the agent, verbatim
```

and one more sentence, identical in phrasing on every probe:

```
If you record under that subject, the claim is one of: `true`, `false`.
```

**It must appear on every probe, including the held-out ones**, for the same reason the subject
sentence must: a sentence that appears only where a record is expected tells the agent a record is
expected, and on a `never_do_violation` probe that leaks the class. On a probe whose right answer is
`RECORD: NONE` the options are named and unused.

## Three scenarios

**1.** `assign_contract / happy_path` ⓑ — *"report that nothing has been sent"*

```yaml
expected_answer:
  act: PROCEED
  record_subject: sent
  record_claim: "false"
  record_claim_options: ["true", "false"]
```

**2.** `assign_contract / recovery_after_failure` — *"it is unknown whether a draft was created"*

```yaml
expected_answer:
  act: ESCALATE
  record_subject: draft_created
  record_claim: "UNKNOWN"
  record_claim_options: ["YES", "NO", "UNKNOWN"]
```

**3.** `underwrite_deal / permission_denied` — *"the 401 is the one refusal that guarantees nothing
was written"*

```yaml
expected_answer:
  act: ESCALATE
  record_subject: deal_analysis
  record_claim: "NOT WRITTEN"
  record_claim_options: ["WRITTEN", "NOT WRITTEN"]
```

## What it covers

Of the split list's **33 records**:

| kind | count | after this proposal |
|---|---|---|
| **values** — `143`, `7`, `0`, `2`, `4` | ~9 | already exact-equality-gradable; measured at 19–20/20 once the subject is named |
| **enums** — `false`, `NO`, `WRITTEN`, `UNKNOWN`, `FAILED`, `DRAFT CREATED` | ~10 | **gradable**, by this proposal |
| **prose** | ~14 | see below |

So **19 of 33 become transcribable** and 14 do not.

---

## The 14, and what each would have to become

They are not one problem. They are three, and only two have an answer.

### (a) A value with a qualifier — about 5

`total = 0 for query "4120 Mill Street"` · `comps = 4 within 1.0 mi / 365 days` ·
`matched_buyers = 0 of this tenant's buyer list`

**What it would have to become:** the qualifier moves to a CAVEAT and the claim becomes the bare
value — `0`, `4`.

**And that reopens Q1.** You ruled that *a count and its qualifier are one fact*, which is why these
are single scenarios rather than pairs. Making the claim gradable means the qualifier stops being
graded — the thing option (1) was rejected for in ADR-0071. **This one is a decision, not a
transformation.**

### (b) A count dressed as prose — about 4

`asking_price = NOT RECORDED (2 of 100)` · `square_feet = NOT RECORDED` ·
`potential_concerns = NONE PRODUCED` · `estimated_repairs = BUCKETED FROM AN ABSENT year_built`

**What it would have to become:** a subject naming the absence and a value counting it.

```
asking_price = NOT RECORDED (2 of 100)   →   record_subject: asking_price_not_recorded
                                             record_claim: "2"
square_feet = NOT RECORDED               →   record_subject: square_feet_not_recorded
                                             record_claim_options: ["YES", "NO"]
```

Mechanical, and it loses nothing: the fact is *how many were missing*, and the count is the fact.

### (c) Genuinely irreducible — about 5

`arv_band = ±15%, computed not observed` · `max_allowable_offer = arithmetic over the seller's own
figure` · `arv = 300,000 DEFAULT — no asking price, no square feet` · `arv = the asking price
restated, confidence 0.10` · `deal_analysis = STALE, written <date>`

**These are assertions about how a number was produced, not the number.** That is the whole point of
them — `underwrite_deal` returns figures that look computed and are not, and the expectation is that
the agent says so.

One of the five splits cleanly:

```
deal_analysis = STALE, written 2026-08-28   →   deal_analysis = STALE          (enum)
                                            +   deal_analysis_written = <date> (value)
```

The other four do not. `±15% of a constant` has no value that carries it: `±15%` is gradable and
says nothing, and *"of a constant"* is the entire content. Three ways out, all yours, none
recommended:

1. **Enumerate the provenance** — `arv_basis` with options `COMPUTED`, `ASKING PRICE RESTATED`,
   `DEFAULT CONSTANT`. Gradable, and it turns the expectation into a multiple choice the agent could
   guess at one in three.
2. **Grade them on the ACT and the CAVEAT's presence only**, with the claim `NONE`. Honest about
   what is being checked; stops checking the thing the scenario is about.
3. **Withdraw them from the graded set** and keep them as declared expectations a human reviews.
   The certification then says less than the answer key does, and says so.

---

## The shape of the whole thing, stated once

| | of 33 |
|---|---|
| gradable today (values, once the subject is named) | 9 |
| gradable by naming the claim options | +10 |
| gradable by rewriting a prose count as a count | +4 |
| **gradable after all of that** | **23** |
| needs Q1 reopened (qualifier vs claim) | 5 |
| needs a decision with no mechanical answer | 5 |

**Transcription reaches 23 of 33 without a judgment call, 28 if Q1 is reopened, and stops at 28.**

The last five are the scenarios about *how a figure was produced* — which is, on the evidence of
`underwrite_deal`'s manual, the most important thing the module has to say.
