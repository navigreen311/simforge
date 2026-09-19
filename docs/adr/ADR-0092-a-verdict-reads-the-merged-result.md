# ADR-0092 — A verdict reads the merged result

**Status:** accepted · **Decided by:** Ivan Green, 19 September 2026 · **Rulings 1, 2 and 4 built;
ruling 3 executed against the database.**
**Follows:** [ADR-0089](ADR-0089-the-submitted-half-runs-inside.md), which made this possible.

---

## The rulings

**1. A verdict reads the merged result, not the held-out half.** *An agent that fails a competence
dimension is not certified, whatever the held-out attempts scored. `outcome.passed` reading only
`report.passed` is the defect.*

**2. The breadth rule asks whether competence was demonstrated, not whether it ran.** *Counting a
FAIL as "exercised" reads a failure as coverage.*

**3. The four certified rows are void.** *They certify agents that failed three of five competence
dimensions. The two failed rows stand.*

**4. A certification records the scenario-set hash it was graded against.** *Today the binding is
inferred from the instruction hash and written down nowhere.*

---

## What happened

On 19 September a battery ran against the six Greenstone runs opened at Gate 8 that morning. Four
came back `certified`. Each of those four rows carries three competence dimensions at **FAIL 0.0**.

Nothing raised. Two numbers were computed from two different things and nothing joined them:

```
battery.py   passed = report.passed                        the HELD-OUT attempts, only
battery.py   results = merge_dimension_results(submitted, held_out)
operation.py elif not outcome.passed: FAILED               reads the first, never the second
```

`ExamReport.passed` is `all(attempt.passed for attempt in self.attempts)`. Every held-out probe
passed — three attempts, eleven probes, score 1.0 each time. Every submitted competence class
failed. The row reported the first as its verdict and the second as its record.

**Until ADR-0089 this could not happen.** `submitted_rubric_results` was always empty, `results`
*was* the held-out result, and the two agreed by construction. Wiring the submitted half in made
them able to disagree and nothing was added to make the verdict read the merge. That is this
repository's own change, three days old.

**The breadth rule was the second line of defence and it did not hold either.**
`is_competence_unexercised` counted a class as exercised when `verdict in (PASS, FAIL)`. Five
competence classes, all FAIL, read as a broad run.

## Built

**Ruling 1, twice over.** `build_gate_result_request` derives `passed` from the merged list it
actually carries — `report.passed and not _any_dimension_failed(results)`. And the gate-result
handler applies the same rule to any payload that arrives, because the rule is about the
certification rather than about who computed the boolean.

**Not a 422.** A submitter reporting a dimension FAIL is telling the truth about the exam; refusing
the payload would lose the result. The verdict is corrected, the record is kept whole, and a
`gate_result_pass_contradicted_by_its_own_dimensions` warning names the disagreement.

**Ruling 2.** `demonstrated` is PASS only. FAIL, NOT_RUN and `not_applicable` all leave the
competence half undemonstrated — the first is something to refuse on, the other two are absences.
Silence still returns False, because `is_evidence_absent` is the withhold that speaks to an empty
result and one fact should produce one reason.

**Ruling 4.** `scenario_set_hash` over the keys actually **put**, in authored order, covering every
field the grader compares. It rides on `AgentRunOutcome` and lands in a new
`OperationCertification.scenarioSetHash` column.

Two decisions inside it. The digest is over the **keys**, not the instructions — an edited or added
key changes the exam without moving the instruction hash by a byte, which is the whole reason the
column exists. And an empty set hashes to **`None`, not `sha256("")`**: a held-out-only exam was
graded against no answer key, and a digest of nothing would claim it was graded against one.
Unputtable keys are excluded, so two exams that asked identical questions hash identically.

### What ruling 1 does not settle, and it is left open on purpose

**`score` is still the held-out pass rate, so a `failed` row may now carry `score 1.0`.** A merged
score would be a new measure, and this repository versions its measures deliberately (ADR-0070)
rather than redefining one in passing. The verdict is what the ruling names. What number belongs
beside it is Ivan's to settle.

## Ruling 3 — what was voided, and what it cost

The four rows are `revoked`, `maxCertifiedTrustTier` cleared, `reviewedBy = ivan-green`, with one
HIGH `SF-OPVOID` incident each naming the failing dimensions — the same mechanism the content-hash
VOID rule uses, which is where "why a certification was revoked" already lives. The six rows were
backed up first. **Zero `certified` cre-forge rows remain.** The two `failed` rows were not touched.

**Nothing outside SimForge had read them.** The Office's `certification` table has not been written
since 16 September, `provisioning_gate_result` since 18 September, and `sweep_run` has never
recorded a `verdict_ingest` pass at all. The four rows never left this database.

## What the six rows would have been — replayed, not asserted

Through the corrected predicates, against the backup taken before the void:

| module / agent | as issued | ruling 1 | ruling 2 withholds | corrected |
|---|---|---|---|---|
| assign_contract / `cc49a49c` | failed | fails | yes | **failed** |
| assign_contract / `c8afb0e6` | failed | fails | yes | **failed** |
| buyer_match / `cc49a49c` | **certified** | fails | yes | **failed** |
| buyer_match / `c8afb0e6` | **certified** | fails | yes | **failed** |
| comp_analysis / `e27fc174` | **certified** | fails | yes | **failed** |
| property_lookup / `e27fc174` | **certified** | fails | yes | **failed** |

**All six are `failed`, and each is caught twice.** The two `assign_contract` rows were already
failed and stay failed — now for five failing dimensions rather than for one attempt in three.

The two rulings are not redundant. Ruling 1 fires on the dimensions and produces `failed`; ruling 2
fires on the classes and produces `provisional`, and `failed` wins the ordering. Ruling 2 is what
catches the run that passes every dimension it ran while demonstrating no competence at all — the
case ruling 1 cannot see.

## Tested

`test_a_verdict_reads_the_merged_result.py`, nine tests, whose fixtures are the exact per-class and
per-dimension shape the voided `buyer_match` row carried:

- the exact payload that certified on 19 September now writes `failed`
- one failing dimension is enough — not a threshold, not a majority
- a clean merged result still reaches `certified` at the `propose` ceiling
- the dimensions are still recorded on the failed row
- the digest changes when a key is edited or added, and not otherwise
- an empty key set hashes to `None`
- an unputtable key is not in the digest
- the hash reaches the certification row, and is null when no key was put

Plus, in `test_the_breadth_rule.py`: `test_a_submitted_class_that_FAILED_still_counts_as_run` is
**reversed** and renamed, with its old reasoning quoted and what was wrong with it named, and
`test_the_four_certified_rows_of_19_september_would_be_caught_twice` pins the real per-class shape.

Suite: **1,119 pass, 2 skip.** `SCHEDULER_ENABLED` stays off.

### One test moved, and it was the right kind of failure

Adding `VERDICT_FAIL` to the router broke `test_the_router_cannot_reach_the_battery`: importing it
from `held_out_scoring` made the held-out grader reachable from a request handler, which ADR-0050
forbids. The constant is defined in `rubric.py`, which the router already reaches, so the import
moved there. The walk caught a real violation on its first opportunity.
