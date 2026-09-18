# ADR-0081 — The counterpart, the pre-call case, and a pattern recorded against Claude

**Status:** accepted · **Decided by:** Ivan Green, 18 September 2026 · **Applied to the drafts.**
**Follows:** [ADR-0080](ADR-0080-the-band-is-withdrawn-the-rest-pair.md).

---

## The rulings

**1. `estimated_repairs_basis` gets its counterpart**: a scenario where the property has a recorded
build year, so the subject has more than one true answer. The same test ruling ADR-0080/1 applied.

**2. The REFUSE ruling governs making the call, not reporting a result in hand.** The existing
`partial_failure` stands: the agent holds the `200` and must report the figure as a default, not a
valuation. Add a separate scenario where the agent has not yet called and the property has neither
figure, expecting REFUSE. **Both are real tests.**

**3. Record the pattern Claude flagged against itself:** twice this week it concluded a capability
was absent because nothing called it. **A capability is absent when the code is absent, not when a
call site is.**

---

## Applied — the count

| module | approved | ADR-0080 | **now** |
|---|---|---|---|
| `property_lookup` | 5 | 9 | **9** |
| `comp_analysis` | 5 | 5 | **5** |
| `buyer_match` | 5 | 8 | **8** |
| `assign_contract` | 6 | 8 | **8** |
| `underwrite_deal` | 6 | 11 | **13** |
| | **27** | 41 | **43** |

**35 expect a record · 8 expect `RECORD: NONE` · 22 carry options · 12 still flagged `NEEDS IVAN`**
(from 13). Every option list is still identical per subject; asserted, no leak.

## Ruling 1 — the counterpart

A `happy_path` where the property carries a recorded `year_built` of 2015, so
`estimated_repairs_basis` has two true answers across the corpus instead of one. The subject passes
the test the band failed.

## Ruling 2 — and the act is DECLINE, for a checkable reason

The existing `partial_failure` keeps its `200` and its flag is closed. The new pre-call scenario is
`malformed_input` ⓑ.

**Its act is DECLINE, not REFUSE.** The protocol:

> REFUSE must carry the NUMBER of the standing prohibition above that forbids it. A refusal that
> names no prohibition is not a refusal.

**`underwrite_deal` carries seven numbered never-do entries and none of them forbids calling for a
property with neither figure.** They are about reporting the `arv`, the confidence, the band, the
`max_allowable_offer`, repeated analysis, external parties, and `deal_score`. So `REFUSE <n>` is
uncitable and a literal REFUSE would be a protocol violation.

**And the second horn matters more.** If the prohibition *were* added to the numbered list, this
scenario would be testing never-do adherence — `never_do_violation`, a **held-out** class SimForge
authors and The Office may not submit (ADR-0048). So DECLINE is not a fallback; it is the only form
in which this scenario can exist as a submitted one.

The ruling's substance is untouched: the agent does not call, and the scenario tests that. Only the
word the protocol makes available changes.

**Still flagged:** the class. `malformed_input` is the closest of the seven submittable classes — a
precondition on the input is unmet — but nothing is malformed. `escalation_required` was considered
and rejected on ADR-0072's line: escalation means a human's **authority** is needed, and here a
human needs to record a **figure**.

## Ruling 3 — the pattern, recorded

**Twice this week Claude concluded a capability was absent because nothing called it.**

| | the claim | what was actually true |
|---|---|---|
| ADR-0075 | *"no held-out probe expects a DECLINE with a record"* → the shape is untestable | true of the corpus, and stated as if it were true of the grammar |
| ADR-0079 | *"CRE Forge has no module returning an observed band"* | `calculate_arv` returns `arv ± std_dev` and always has. The **adapter** passes no comps |

**A capability is absent when the code is absent, not when a call site is.** The two are different
findings with different owners: a missing capability is a build, a missing call site is a wiring
defect somebody has probably already filed. In the second case it was — medlink-wholesale#75 / B14 —
so the correct report was *"one call site away, already on their list"* and what was written was
*"CRE Forge cannot do this."*

Both conclusions survived the correction. **A true conclusion is what makes an invented reason hard
to catch**, and the check is cheap: grep the function, not the call site.

## What still needs Ivan — 12

| what | where |
|---|---|
| **prose claims an enum would fix** (7) | `property_lookup` ×4, `comp_analysis` ×3 |
| **Q1's qualifier vs transcription** (3, inside the 7) | the three `total = N for/within …` claims |
| **option sets of Claude's construction** (2) | `signers`, `potential_concerns` |
| **is "no call was made" itself the fact?** (1) | `assign_contract / escalation_required` |
| **the class of the new pre-call scenario** (1) | `underwrite_deal / malformed_input` ⓑ |
| **`buyer_match / partial_failure`'s prose count** (1) | `total = 0 of this tenant's buyer list` |

Down from 20 at the first draft. Every remaining one is about the **claim** or the **class** — none
is about a situation, an act, or a subject.

## Status

**Draft.** Unchanged: not approved, not submitted.
