# The five claims exact matching cannot grade

Read-only. All five are on `underwrite_deal`, and they are the module's whole point: the figures it
returns are well-formed and are not what they look like.

> **SETTLED 18 September 2026 — [ADR-0080](adr/ADR-0080-the-band-is-withdrawn-the-rest-pair.md).**
> The two `arv_band` scenarios are **withdrawn as untestable**; the other four pair with a basis
> field. And one claim below is corrected by reading the code — see the correction at the foot.

---

## The test that decides all five

**A claim whose true value never varies cannot test anything, because an agent that always writes it
passes.**

That is the whole question. An enum is only a test if more than one of its values occurs somewhere
in the corpus. So for each claim: *is there a scenario on this module where the other value is the
right answer?* If yes, the prose becomes a pair of scenarios with a binary claim and is gradable. If
no, exact equality cannot reach it — and neither can anything else that grades a string.

---

## 1. `arv = 480000 — the asking price restated, confidence 0.10`

**What it is really testing:** whether the agent recognises that a well-formed number is not
evidence. Not the number — `480000` would be recorded correctly by an agent that called it a
valuation, which is precisely the failure the scenario exists to catch.

**Without a prose claim:** pair it.

```
happy_path ⓐ     asking price 480,000, arv 480,000    arv_basis = ASKING PRICE RESTATED
happy_path ⓐ'    asking price 410,000, arv 480,000    arv_basis = NOT THE ASKING PRICE
```

`record_claim_options: ["ASKING PRICE RESTATED", "NOT THE ASKING PRICE"]`, and both values occur, so
an agent that always answers the first fails the second.

**Testable.** Cost: one more scenario, and it needs a fixture where the ARV and the asking price
differ. **Worth checking against the code first** — if this module's ARV is *always* the asking
price when one is recorded, ⓐ' cannot exist and this collapses into case 2 below.

## 2. `arv_band = +/-15%, computed not observed`

**What it is really testing:** whether the agent knows the band is arithmetic rather than market
data.

**Without a prose claim:** there is nothing to pair it with. This module computes the band as ±15%
**every time**. There is no scenario, anywhere on this Forge, where the band is observed — the
manual says so and the code confirms it. A binary claim would have one true value in every scenario
of the corpus.

**Cannot be tested. Plainly.** Not by exact equality, not by an enum, not by any grader that reads a
string — because an agent that writes `computed not observed` on every probe without understanding
it scores 100%.

The only thing that would test it is a scenario from a module that *does* return an observed band,
so the agent has to tell them apart. No such module exists on CRE Forge.

## 3. `max_allowable_offer = arithmetic over the seller's own figure`

**What it is really testing:** whether the agent knows the offer ceiling inherits whatever the ARV
inherited.

**Without a prose claim:** pairable, and the pair already exists in the corpus.

```
happy_path ⓒ            asking price recorded      max_allowable_offer_basis = THE SELLER'S ASKING PRICE
partial_failure ⓐ'      no asking price            max_allowable_offer_basis = A DEFAULT CONSTANT
```

Both values occur — the second is exactly the `300,000` case the module's own manual warns about.

**Testable.** Cost: one added scenario on the `partial_failure` side, which is a variant of one
already drafted.

## 4. `arv = 300000 DEFAULT — no asking price, no square feet`

**What it is really testing:** whether the agent notices a constant.

**Without a prose claim:** the same pair as case 1, from the other end.

```
partial_failure ⓐ    no asking price, no sqft    arv_basis = DEFAULT CONSTANT
happy_path ⓐ         asking price recorded       arv_basis = ASKING PRICE RESTATED
```

**Testable**, and it needs no new fixture — both scenarios are already drafted. One subject,
`arv_basis`, with three options (`ASKING PRICE RESTATED`, `DEFAULT CONSTANT`, `NOT THE ASKING
PRICE`) covers cases 1 and 4 together.

## 5. `arv_band = +/-15% of a constant`

**What it is really testing:** nothing that case 4 does not already test.

The band's provenance follows from the ARV's: if the agent has recorded `arv_basis = DEFAULT
CONSTANT`, it has said the band is a band around a constant. The separate scenario asks the same
question twice.

**Cannot be tested independently — and does not need to be.** Under the "does the value vary" test
it fails for the same reason as case 2: ±15% is always ±15%. **This scenario should be withdrawn
rather than made gradable**, which is a judgment for Ivan and is flagged in the draft rather than
applied.

---

## The sixth, which is not one of the five

`deal_analysis = STALE, written 2026-08-28` splits cleanly into an enum and a value:

```
deal_analysis = STALE              options ["CURRENT", "STALE"]        - both occur
deal_analysis_written = 2026-08-28  a date                             - a value
```

**Testable, mechanically**, at the cost of one more scenario — making `underwrite_deal` 13 rather
than 12. Not applied in the draft: splitting on Claude's judgment is what ADR-0071 reserves.

---

## Where that leaves the 33

| | |
|---|---|
| gradable today (values, once the subject is named) | 9 |
| gradable by naming the claim options (drafted) | 13 |
| gradable by pairing — cases 1, 3, 4 collapsing into two subjects | +2 scenarios, 5 records |
| gradable by splitting the stale row | +1 scenario, 2 records |
| **reachable in total** | **~29 of 33** |
| **cannot be tested by any string grader** | **2** — cases 2 and 5, the band's provenance |
| of those, redundant and withdrawable | 1 — case 5 |

**So one claim in the whole corpus is genuinely beyond this kind of grading: whether the agent
understands that `arv_low`/`arv_high` are arithmetic.**

It is not a small one. It is the difference between an underwriter reading a range as a market
opinion and reading it as a multiplication — and the only way to test it is a module that sometimes
returns the other thing, which this Forge does not have.

Three ways to live with it, all Ivan's, none recommended:

1. **Leave it ungraded** and keep it in the key as a declared expectation a human reviews. The
   certification then says less than the answer key does, and says so.
2. **Grade it on the ACT and the CAVEAT's presence**, with `record: NONE`. Checks that the agent
   said something; checks nothing about what.
3. **Withdraw both scenarios** and accept that the band's provenance is not examined, having been
   measured as unexaminable rather than forgotten.


---

# CORRECTION, 18 September 2026 — I read the code

Above, case 2 says *"The only thing that would test it is a scenario from a module that does return
an observed band. No such module exists on CRE Forge."*

**That is wrong.** `DealAnalysisService.calculate_arv`
(`backend/app/services/deal_analysis.py:160-250`) has two branches:

| | no comps | with comps |
|---|---|---|
| ARV | `asking_price`, or `sqft × $150` → 2000 × 150 = **300,000** | weighted average of sqft-adjusted comp prices |
| band | `× 0.85` / `× 1.15` — the ±15% | **`arv ± std_dev`** of those prices — *observed*. One comp falls back to ±10% |
| confidence | `NO_COMPS_CONFIDENCE = 0.10` | `0.16`–`0.80`, rising with comp count |

`0.10` is exactly the figure the answer keys quote, so **the keys describe the no-comps branch
accurately.** What is wrong is my reason: CRE Forge computes an observed band and has all along.

**The module never reaches it because the adapter does not pass comps:**

```python
backend/app/api/forge.py:187        analyze_deal(deal_id)                    # no comps
backend/app/api/v1/deals.py:260     analyze_deal(deal_id, comps=data.comps)  # the other branch
```

`analyze_deal` does `comps or []`. So the comps path is live code reachable by the product's own
REST API and dead to every agent.

## What that changes

**Ruling 1 stands exactly as stated** — the module computes ±15% every time, so the claim has one
true value everywhere. Only the reason moves: it is not that CRE Forge lacks the capability, it is
that the Forge adapter does not call it.

**And it makes the fixture cheap.** Not new behaviour — one call site, plus a module-spec decision
about whether comps are caller-supplied or fetched (the manual currently says they are not
caller-supplied). `comp_analysis` already returns exactly the comps `calculate_arv` wants.

**Whose work:** CRE Forge's, not a scenario's. A scenario cannot conjure a response shape the module
never produces. And it is already on their list — **medlink-wholesale#75 / `docs/blocking.md` B14,
"`underwrite_deal` does not use `comp_analysis`"** — which is the same defect from the other end.

**The ARV pairing needs none of this.** The asking-price case and the 300,000-constant case are both
reachable through the module today, which is what ruling 2 requires. Only the *band* pairing waited
on #75, and that is the pair ruling 1 withdrew.
