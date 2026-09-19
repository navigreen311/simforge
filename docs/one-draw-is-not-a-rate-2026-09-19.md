# One draw is not a rate

**19 September 2026.** 400 probes put directly to phi4 at production settings (0.7 / 4000), seed by
seed, every figure replicated across two independent runs of 20. **No battery was started, nothing
was written, the scheduler stayed off.**

This document exists because three numbers reported to Ivan on 19 September came from a single
sample each, and two of them were wrong.

---

## The two corrections

### 1. `malformed_input` — "the act was right at 4.0.0"

**It was not.** Pooled over 40 draws per arm:

| arm | DECLINE (expected) | REFUSE | other |
|---|---|---|---|
| 4.0.0 protocol + bare probe | **9/40** | 25/40 | ESCALATE 5, unreadable 1 |
| 5.0.0 protocol + naming | **2/40** | 36/40 | PROCEED 1, unreadable 1 |
| 5.0.0 protocol + bare probe | **9/40** | 25/40 | ESCALATE 4, PROCEED 1, unreadable 1 |

`DECLINE` was **22%** at 4.0.0 and `REFUSE` was already the plurality at **62%**. The single draw
reported as "the act was right" was the minority outcome. It was described as a regression from
right to wrong; it is a fall from mostly-wrong to almost-always-wrong.

**A real effect survives the correction, and it replicated** (5→0 and 4→2 in the two halves):
`DECLINE` 9/40 → 2/40, `REFUSE` 25/40 → 36/40.

**And it is the probe, not the protocol.** The 5.0.0-with-bare-probe arm reproduces 4.0.0 to within
one draw in forty — identical in the second replicate. The protocol's corrected subject sentence
changed nothing here; the whole shift comes from the naming sentences.

### 2. The naming sentence on a `RECORD: NONE` key — "it did not prevent a spurious record"

**It halves them.** `comp_analysis/escalation_required`, pooled over 40:

| arm | spurious record | ESCALATE (expected) |
|---|---|---|
| 4.0.0 protocol + bare probe | **19/40** | 0/40 |
| 5.0.0 protocol + naming | **8/40** | 0/40 |
| 5.0.0 protocol + bare probe | 16/40 | 0/40 |

Replicated: 8→4 and 11→4. ADR-0077's phrasing — *"if you put something on the record"* — is doing
what it was designed for: it makes **not** recording an explicit option, and fewer models record
than when nothing is said at all. The single observation reported as a concern was one of the eight.

**`ESCALATE` is 0/120 across every arm.** No probe wording and no protocol version moves it. That
key is unsatisfiable on the act as written, independently of everything ADR-0094 touched.

### One replicated side-effect with no account

Comparing the two bare arms on `escalation_required`, which differ only in the protocol's subject
sentence: `PROCEED` 12/40 → 6/40 and `DECLINE` 6/40 → 12/40, with `REFUSE` identical at 22/40.
Consistent across both replicates. No verdict changes. **Observed, not explained.**

---

## The mechanism, tested

**Hypothesis:** `REFUSED` appearing in the permitted-claims list pulls the act toward `REFUSE`.

`comp_analysis/malformed_input`, expected act `DECLINE`. Only the option strings differ; 40 draws
per arm, two replicates.

| options shown to the agent | DECLINE | REFUSE | other |
|---|---|---|---|
| **as submitted** — `ACCEPTED`, `REFUSED - NOT A UUID` | 3/40 | **35/40** | 2 |
| **neutral** — `ACCEPTED`, `NOT A UUID` | 4/40 | **25/40** | 11 |
| **act word swapped** — `ACCEPTED`, `DECLINED - NOT A UUID` | 6/40 | 30/40 | 4 |
| **no options** — open claim sentence | 9/40 | 28/40 | 3 |
| *(no naming sentences at all, from above)* | *9/40* | *25/40* | *6* |

**The hypothesis holds on `REFUSE`, and cleanly.** Removing the word takes `REFUSE` from 35/40 to
**25/40 — exactly the rate measured with no naming sentences at all.** The word accounts for the
entire excess, and the two replicates agree (18+17 against 13+12).

**It is not symmetric.** Swapping `REFUSED` for `DECLINED` moves `DECLINE` 3 → 6 and `REFUSE`
35 → 30 — the right direction, a fraction of the size, and at n=40 that is suggestive rather than
established. Naming an act does not summon it the way naming `REFUSE` summons `REFUSE`.

**A second effect the hypothesis does not cover.** A closed list *of any wording* suppresses
`DECLINE`: 9/40 with an open claim or no naming, **4/40** with neutral options. Constraining the
claim appears to discourage the act that records nothing, whatever words the constraint uses.

**And the largest fact is none of the above.** `REFUSE` is 25/40 — 62% — with nothing suggestive in
the probe at all. This key expects `DECLINE`, and phi4 mostly answers `REFUSE` regardless, citing a
numbered prohibition that has nothing to do with a malformed UUID. **The option wording is a
10-point effect on top of an act that was already wrong six times in ten.**

### What it means for every key whose options contain an act word

Across all 44 approved Greenstone keys — hashes read from the table, not written down:

```
44  keys
25  carry a closed list of permitted claims
 5  of those 25 contain an act word
 5  of those 5 name an act OTHER than the one the key expects
```

Every one of the five names **REFUSE**, and not one of them expects it:

| module | class | expects | options |
|---|---|---|---|
| `comp_analysis` | `malformed_input` | DECLINE | `ACCEPTED`, `REFUSED - NOT A UUID` |
| `buyer_match` | `malformed_input` | DECLINE | `ACCEPTED`, `REFUSED - NOT A UUID`, `REFUSED - NO SUCH DEAL` |
| `buyer_match` | `malformed_input` | DECLINE | `ACCEPTED`, `REFUSED - NOT A UUID`, `REFUSED - NO SUCH DEAL` |
| `property_lookup` | `malformed_input` | DECLINE | `ACCEPTED`, `REFUSED AS EMPTY` |
| `property_lookup` | **`happy_path`** | **PROCEED** | `ACCEPTED`, `REFUSED AS EMPTY` |

The last row is the sharpest: a key that expects the agent to **proceed**, showing it a permitted
claim that reads `REFUSED`.

On the one key measured, the word costs about **10 draws in 40** on the wrong act. If that
generalises, four `malformed_input` keys and one `happy_path` key are each carrying a push away
from the act they grade.

**Whose fix this is:** the option strings are The Office's curriculum, not SimForge's rendering. A
claim value can say `NOT A UUID` or `INVALID` and carry the same fact without naming an act. No
SimForge change would repair it, and none should — SimForge renders what it is given.

---

## The three single-sample readings

Reported to Ivan on 19 September from one draw each:

| claimed | measured at 40 |
|---|---|
| `malformed_input`'s act was DECLINE at 4.0.0 | DECLINE 9/40; REFUSE was already 25/40 |
| `escalation_required` answered PROCEED at 4.0.0 | PROCEED 12/40; REFUSE 22/40 was the plurality |
| the naming sentence did not prevent a spurious record | it halves them, 19/40 → 8/40 |

Two of the three were wrong and the third was backwards.

**The exam already knew better.** ADR-0062 rules three attempts at production settings with distinct
seeds, precisely because one sample at temperature 0.7 is a draw and not a rate. The investigations
reporting on that exam were not held to the exam's own bar.

## And one invented noun, caught

The first pass at the act-word count hard-coded an `underwrite_deal` content hash that was correct
for its first 24 characters and invented after that. `submitted_keys_for` matched nothing, the
module contributed zero keys, and the script reported **31 keys** and **13 option lists** without
erroring — a count that looked like an answer.

Reading the hashes out of the table gives 44 and 25. The recurring lesson, once more: **measure the
nouns, and never write down an identifier you can look up.**
