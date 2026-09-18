# ADR-0082 — The twelve flags are answered

**Status:** accepted · **Decided by:** Ivan Green, 18 September 2026 · **Applied to the drafts.**
**Follows:** [ADR-0081](ADR-0081-the-counterpart-the-precall-case-and-a-pattern.md). **Closes:** every
open question on the split keys.

---

## The count

| module | approved | ADR-0081 | **now** |
|---|---|---|---|
| `property_lookup` | 5 | 9 | **10** |
| `comp_analysis` | 5 | 5 | **5** |
| `buyer_match` | 5 | 8 | **8** |
| `assign_contract` | 6 | 8 | **8** |
| `underwrite_deal` | 6 | 13 | **13** |
| | **27** | 43 | **44** |

**37 expect a record · 7 expect `RECORD: NONE` · 25 carry options · 4 carry an `expected_caveat`.**

**`NEEDS IVAN`: 0.** Every option list is still identical per subject; asserted, no leak.

---

## The rulings, applied

| # | ruling | effect |
|---|---|---|
| 1 | signers: keep `VERIFIED` as an unreachable distractor | note rewritten with the reason |
| 2 | concerns: plain counts, `2` and `0`, per Q5 | options removed |
| 3 | refused property id: adopt the pair, note the missing counterpart | options added, gap recorded |
| 4 | unrecorded prices: `asking_price_not_recorded = 2` | a count |
| 5 | unrecorded square footage: a count | `square_feet_not_recorded = 1` |
| 6 | empty query: adopt the pair **and** add the counterpart | **+1 scenario** |
| 7–10 | the qualifier: grade the bare count exactly, expect a caveat carrying the qualifier | `expected_caveat` on four scenarios |
| 11 | the pre-call scenario is `partial_failure` | re-classed |
| 12 | record `contract_created = NO` | `RECORD: NONE` → a record |

## Ruling 1 — why the distractor is not the band

The two look alike and are opposites, and the ruling says which is which:

> **An unreachable *wrong* answer tests something. An unvarying *right* one does not.**

The band was withdrawn because the right answer never varied, so an agent that always wrote it
passed without knowing anything. `VERIFIED` also never occurs — but the agent must **choose**, and
choosing it means believing a signer was checked. The distractor is not noise; it is the failure the
scenario exists to catch, offered in a form the agent can take.

## Ruling 2 — and what a count stops carrying

`potential_concerns = 0`, no options. The mixed list was Claude's construction and contradicted Q5,
which ruled the record is the **count** of concerns reported — so an empty list is `0`.

**What the count does not carry:** `failure_signatures.silent_partial` says an empty list is the
matcher producing none rather than a clearance, and a `0` says only the number. That sentence now
lives in `expected_behavior` and is not graded. Named, not hidden.

## Rulings 7–10 — and the answer to the question they asked

**Caveat presence is not gradable today.** The data is there and nothing reads it:

```
AgentAnswer.caveats          parsed by _CAVEAT_RE, battery.py:431
ObservedBehaviour.disclosed  written at battery.py:531  —  read at NO site
```

`grep -rn "\.disclosed"` across `apps/api/src` returns **one line, the write.** So the field is
typed, populated and consulted by nothing.

**Recorded, as the ruling requires: the qualifier on those four scenarios is an expectation no
grader reaches.** It is one predicate away — the value already travels — but the grader that would
read it is P2's submitted-scenario runner, which is unbuilt.

This is the shape ADR-0081 ruling 3 named, arrived at correctly for once: the **capability** (parsing
a caveat) is present, the **call site** (grading it) is absent, and those are two different findings.

The four affected, and what each caveat carries:

| scenario | graded | in the caveat, ungraded today |
|---|---|---|
| `property_lookup / partial_failure` | `total = 0` | the query string the count belongs to |
| `comp_analysis / happy_path` | `total = 4` | the radius and the age window |
| `comp_analysis / partial_failure` | `total = 0` | the radius, age and count constraints |
| `buyer_match / partial_failure` | `total = 0` | that the zero is about a hand-built list |

`comp_analysis / happy_path` is the sharpest: `correct_sequence` exists to require the parameters
beside the count, so the caveat there is not decoration, it is the instruction.

## Ruling 11 — the class

`partial_failure`. Nothing is malformed; **incomplete data was recognised**, which is
`failure_recognition`, and recognising it *before* the call rather than after is the only difference
from its sibling.

---

## The two recorded gaps

Neither is an open question. Both are known holes with their reasons written down.

1. **No grader reads caveats**, so the qualifier on four scenarios is unreached. Above.
2. **`comp_analysis / property_id` has no counterpart.** Ruling 3 said adopt *and note* rather than
   adopt *and pair*, so `ACCEPTED` / `REFUSED - NOT A UUID` has one true value in every scenario of
   that module. Ruling 6 fixed the same shape on `property_lookup` by adding a counterpart; this one
   stands unpaired on purpose.

## Status

**Draft.** Not approved, not submitted — and now with no question left inside them.
