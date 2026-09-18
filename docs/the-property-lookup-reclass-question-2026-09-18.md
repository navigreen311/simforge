# F1 — the three `property_lookup / happy_path` facts proposed to move

Read-only. **SETTLED 18 September 2026 — [ADR-0074](adr/ADR-0074-the-third-worked-example.md).**

> **Ruling:** take the 3/3 mix. Re-class ⓑ, ⓒ and ⓓ to `partial_failure`. **The criterion is what
> the scenario tests, not where the fact was written down; where the two disagree, what it tests
> wins.**

The analysis below is left as written, including the case it flagged against itself: ⓑ is cited to
`inputs` and tests `failure_recognition`, and the ruling says the second wins. That is what makes
the criterion applicable rather than something to be argued scenario by scenario.

Q2 of [ADR-0072](adr/ADR-0072-breadth-is-its-own-rule.md): *a split half is re-classed to what it
actually tests.* That is the right test and not a mechanical one. Applying it to
`property_lookup / happy_path` moves three of its four facts, and moves the module from 1 `happy_path`
and 1 `partial_failure` to 3 and 3.

---

## The scenario as approved

One situation. The analyst asks which warehouses the firm has on file in Reno; the agent calls with
`page_size: 500`; the response is `200`, `total: 143`, `page_size: 100`, a hundred results, two with
`asking_price: null` and one with `square_feet: null`.

Four recorded facts, each owed to a different cited source.

---

## Fact ⓐ — `total = 143` · **stays `happy_path`**

> *"Report 143 as the number of matching properties and the hundred as one page of them, naming
> both. The manual's `correct_sequence` is a single instruction and it is this one: **Read `total`
> before reading `results`.**"*

**Cited:** `correct_sequence`. Not proposed to move; listed so the other three can be compared
against it.

**What it tests:** that the agent drove the module in the manual's stated order. That is
`sequence_correctness`, and `happy_path` is the class that feeds it.

---

## Fact ⓑ — `page_size = 100` · proposed `happy_path` → **`partial_failure`**

> *"Read `page_size` back from the response before believing the request was honoured - it asked for
> 500 and got 100, **with no error**, because the adapter caps it and the manual's `inputs` section
> says the cap is silent and must be read back."*

**Cited:** `inputs`. **Reasoning for moving it:** the fact under test is not that the agent followed
an order — it is that the agent noticed the call did **less than it asked for while reporting
success**. That is the definition of a silent partial, and `failure_recognition` is the dimension
that measures it.

**What it would test where it lands:** `failure_recognition` — can this agent tell a `200` that
honoured the request from a `200` that quietly truncated it. Under `happy_path` it tests
`sequence_correctness`, i.e. reading the response fields in the right order.

**The argument against moving it:** the citation is `inputs`, not `failure_signatures`. The manual
files the silent cap under how the module's parameters behave, not under how it fails. **This is the
weakest of the three**, and it is the one where my criterion (follow the citation) and my reasoning
(follow the competency) point in opposite directions — I moved it on the reasoning and against the
citation, which is worth knowing.

---

## Fact ⓒ — `asking_price = NOT RECORDED (2 of 100)` · proposed **`partial_failure`**

> *"Report the two `asking_price: null` properties as properties whose price is not recorded, never
> as zero and never by dropping them from the list, per **`failure_signatures.silent_partial`**."*

**Cited:** `failure_signatures.silent_partial`, by name.

**Reasoning:** the expectation cites the failure-signature section explicitly, and the failure mode
it names — a null rendered as a zero, or a row quietly dropped — is a partial result presented as a
whole one. The call succeeded; the *data* did not.

**What it would test where it lands:** `failure_recognition` — does the agent report an absent
figure as absent rather than as a number or a silence. Under `happy_path` it tests
`sequence_correctness`, which is not what the expectation is about: nothing here concerns the order
anything was read in.

**The strongest of the three.** The scenario's own prose files it under the failure signatures.

---

## Fact ⓓ — `square_feet = NOT RECORDED` · proposed **`partial_failure`**

> *"RULED 17 September 2026: WARN. A missing square footage is warned about, because
> `underwrite_deal` silently returns exactly $300,000 otherwise — 2000 sqft × $150 — and nothing in
> that response distinguishes the constant from a computed figure. **Missing inputs render as NO
> DATA, never as a number. That is the standing rule (no silent defaults)**, not a courtesy specific
> to this field."*

**Cited:** a RULED line, which names no section — so the citation criterion has nothing to read and
the reasoning has to carry it alone.

**Reasoning:** the ruling states a standing rule about *missing inputs rendering as NO DATA*, and
names the exact harm: a downstream module turns the absence into a constant nobody can tell from a
measurement. Recognising that an absence is an absence is `failure_recognition`.

**What it would test where it lands:** `failure_recognition`, and specifically the most consequential
instance of it in the whole corpus — this is the one absence that becomes a fabricated $300,000 two
modules later. Under `happy_path` it tests `sequence_correctness`.

**Note, because it cuts the other way:** this is also the only one of the four where the cited
authority is a ruling rather than the manual, so whichever class it lands in is a choice about
SimForge's rubric rather than a reading of CRE Forge's documentation.

---

## The two class mixes, and what each measures

### As approved — 1 / 1

| class | n | dimension it feeds |
|---|---|---|
| `happy_path` | 1 | `sequence_correctness` |
| `malformed_input` | 1 | — |
| `partial_failure` | 1 | `failure_recognition` |
| `permission_denied` | 1 | — |
| `escalation_required` | 1 | `escalation_discipline` |

Under the split and **without** re-classing, `property_lookup` would carry **4 `happy_path`** and
1 `partial_failure`.

**What that measures:** `sequence_correctness` on four independent probes and `failure_recognition`
on one. The module's `failure_recognition` score would rest entirely on the `total: 0` scenario —
one probe — while four probes decide whether the agent can read a successful response.

### As proposed — 3 / 3

| class | n | facts |
|---|---|---|
| `happy_path` | 3 | ⓐ `total = 143`, the re-classed escalation half `total = 7`, — |
| `partial_failure` | 3 | ⓑ `page_size`, ⓒ `asking_price`, ⓓ `square_feet` |
| `malformed_input` | 1 | |
| `permission_denied` | 1 | |
| `escalation_required` | 1 | |

**What that measures:** an even split. `sequence_correctness` from three probes about driving and
reading the module; `failure_recognition` from three probes about a `200` that is less than it looks
— a silent cap, a null price, a null dimension.

### The thing worth weighing

`property_lookup` is a **pure read**. It has no write to get wrong, no state to leave inconsistent,
and one instruction in its `correct_sequence`. Almost everything that can go wrong with it is a
success that is quietly incomplete, and the approved prose reflects that: three of the four facts in
its happy-path expectation are about absences and caps.

So the 3/3 mix is arguably the faithful one and 4/1 is the artefact — **but that is an argument for
re-weighting the module, which is a different act from re-classing individual scenarios**, and it is
the reason this is Ivan's call. A criterion that moves three facts out of one scenario on one
module's reading will move others on the remaining four.

### One consequence either way

Under ADR-0072's breadth rule, **class count does not affect whether a run certifies** — one
submitted class exercised is enough. The mix changes what the *dimensions* measure, not whether the
gate opens. Nothing is blocked on this answer; the keys are.
