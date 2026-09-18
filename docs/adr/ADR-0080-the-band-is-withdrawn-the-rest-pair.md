# ADR-0080 — The band is withdrawn, the rest pair

**Status:** accepted · **Decided by:** Ivan Green, 18 September 2026 · **Applied to the drafts.**
**Follows:** [ADR-0079](ADR-0079-the-split-keys-are-drafted.md).

---

## The rulings

**1. The two `arv_band` scenarios are withdrawn, having been measured unexaminable.** The module
computes ±15% every time, so the claim has one true value everywhere and an agent that writes it
without understanding scores 100%. **Record that it is withdrawn as untestable, not forgotten, and
what would make it testable: a module that sometimes returns an observed band.**

**2. The other four pair with a basis field**, as proposed: the agent picks from a named list rather
than writing prose.

**3. `buyer_match / malformed_input` splits into two scenarios, one per branch.** A scenario has one
expected answer.

**4. Flag 3 accepted: `contract_created` as the shared subject.**

---

## Applied — the count

| module | approved | first draft | **after ADR-0080** |
|---|---|---|---|
| `property_lookup` | 5 | 9 | **9** |
| `comp_analysis` | 5 | 5 | **5** |
| `buyer_match` | 5 | 7 | **8** |
| `assign_contract` | 6 | 8 | **8** |
| `underwrite_deal` | 6 | 12 | **11** |
| | **27** | 41 | **41** |

The total is 41 either way, by coincidence: **two withdrawn, two added** — the
`max_allowable_offer_basis` counterpart and the second `malformed_input` branch.

**33 expect a record · 8 expect `RECORD: NONE` · 20 carry `record_claim_options`** (13 before) ·
**13 still carry a `NEEDS IVAN` note** (20 before).

## Ruling 1 — recorded, not deleted

`underwrite_deal.yaml` gains a `withdrawn_as_untestable:` block. Both entries carry `was:`, `why:`
and `what_would_make_it_testable:`, so an expectation dropped on purpose cannot later read as one
nobody thought of.

## Ruling 2 — and the code check that goes with it

`arv_basis` and `max_allowable_offer_basis` are new subjects; `STALE` joins the existing
`deal_analysis` option list rather than becoming a subject of its own.

**Every option list is identical across every scenario that uses its subject**, asserted. If the
options varied per probe the list itself would say which scenario is being put — the same leak the
naming sentence avoids, and it is now checked rather than remembered.

Each basis carries **three** options, and the third is `COMPUTED FROM COMPARABLE SALES`, which is a
true branch of the code that the Forge adapter never reaches. So the pair is a three-way choice
rather than a coin flip, and one option is currently never the answer.

### The correction the code check produced

ADR-0079 said *"CRE Forge has no module returning an observed band."* **Wrong, and corrected here.**

`DealAnalysisService.calculate_arv` has a comps branch that returns `arv ± std_dev` of the
sqft-adjusted comp prices, with a confidence of 0.16–0.80. The Forge adapter never reaches it:
`forge.py:187` calls `analyze_deal(deal_id)` with no comps, while `v1/deals.py:260` passes
`data.comps`.

**Ruling 1 stands exactly as stated** — the module computes ±15% every time. Only the reason moves:
not a missing capability, an adapter that does not call it. Which makes the fixture **one call site
away**, it is **CRE Forge's work rather than a scenario's**, and it is already their open defect
**medlink-wholesale#75 / B14**.

**The ARV pairing needs none of that** — both its cases are reachable through the module today.

## Ruling 3 — the branch that matters

The approved scenario said *"a `422` … or, if the property id happens to be a well-formed UUID, a
`404`."* Now two scenarios sharing one option list.

The 404 branch is the dangerous one and is why the split is worth its cost: **a well-formed UUID for
the wrong object passes the shape check**, so the control that catches it is the deal's existence
rather than the payload's form.

## Ruling 4 — closed

`contract_created` is the shared subject on all four write-certainty scenarios of `assign_contract`,
with one option list. The `NEEDS IVAN` note is removed and replaced with the reasoning.

## What still needs Ivan — 13 notes, and two that change a scenario

- **`underwrite_deal / partial_failure`'s act still contradicts the key's own RULED line.** The
  ruling says *REFUSE — do not call this module for a property with neither an asking price nor a
  square footage*; the situation has the agent already holding the `200`. Untouched by these
  rulings.
- **`estimated_repairs_basis` has one true value everywhere**, which is the condition ruling 1
  withdrew two scenarios for. Its counterpart — a property with a recorded `year_built` — does not
  exist as a scenario. Either it is added or the subject goes the way of the band.

The remaining eleven are prose claims that an enum would fix, and option sets of Claude's
construction awaiting a word.

## Status

**Draft.** Unchanged: not approved, not submitted.
