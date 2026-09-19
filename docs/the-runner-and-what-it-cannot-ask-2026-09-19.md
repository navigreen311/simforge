# P2's grader, and the question it cannot ask

Companion to [ADR-0086](adr/ADR-0086-the-runner-grades-by-transcription.md).

---

## The blocker, first, because it changes what "the runner" means

**SimForge cannot put a submitted probe. There is nothing to ask.**

`OperationScenarioSubmission` carries `expectedBehavior`, `expectedEscalation`,
`instructionSection`, `neverDoEntry` and now the expected answer — and **no situation.** Checked
against the live table and against The Office's generator, whose own comment says it plainly:

> *"The precipitating situation, which is the half of a scenario no manual contains. `summary` is
> the only field on this dataclass that can carry it — **there is no `situation` field on either
> side of the [wire]**."*

The approved keys all have a `situation`. The generator holds it in `summary` and does not send it.

So the runner splits cleanly in two, and only one half was ever SimForge's to build:

| | whose | state |
|---|---|---|
| **the grader** — compare an answer to a stored key | SimForge | **built** |
| **the probe** — put the scenario to the agent | The Office must send `situation` | **blocked, one field** |

Grading an answer to a question nobody can ask is not a useful runner. It is, however, exactly the
half that had to exist first — and building it surfaced the missing field, which two months of
design documents had not.

**Why SimForge must not invent the situation.** The only prose it holds is `expected_behavior`, and
rendering that into a probe would hand the agent the answer. The Office's comment about `summary`
is making the same point from the other end.

---

## What was built

`submitted_scoring.py` — **the first reader `OperationScenarioSubmission` has ever had.** P1 stored
those rows in September and nothing consulted them, which is the shape of the defect P1 itself
fixed one layer down: validated and discarded, then stored and unread.

- `submitted_keys_for(...)` — the keys for one module, in authored order, on the same natural key
  the write uses.
- `grade_submitted(key, answer)` — act, subject and claim by **exact equality**; the caveat by
  **presence**.
- `grade_submitted_module(keys, answers)` — a missing answer is `NOT_RUN`, never a `KeyError`.

**Eight named reasons**, because a cert carrying a bare FAIL tells a reader nothing to act on — and
**every fault fires, not just the first**: an answer with the wrong act *and* the wrong subject says
both, or a fix lands on one and the agent re-sits an exam it fails the same way twice.

Two distinctions worth their own reasons:

- **`recorded_a_claim_that_was_not_on_the_list`** vs **`recorded_a_claim_the_key_does_not_expect`.**
  The permitted claims were *named to the agent*, so writing something else is a different mistake
  from picking the wrong one off the list.
- **A key with no `expected_answer` is `NOT_RUN`, not `FAIL`.** The submitter's omission must not
  land on the agent.

### The one interpretive choice, made visible

**Case is not folded.** You ruled exact equality with no fuzzy matching, so `Total` is not `total`.
Only transport is stripped — surrounding whitespace and the backticks a model wraps an identifier
in.

It bites measurably: in the five-model run **`mistral` wrote subjects in upper case** (`RESULTS`,
`MATCHING_PROPERTIES`) while every other model wrote them lower. Folding case would change verdicts,
which is why there is a test asserting it rather than a quiet `.lower()`.

---

## What each of the seven classes would now score

Across the 44 draft keys, with the dimension each class feeds:

| class | n | expect a record | with options | with a caveat | competence dimension |
|---|---|---|---|---|---|
| `happy_path` | 13 | 13 | 8 | 1 | `sequence_correctness` |
| `partial_failure` | 12 | 12 | 5 | 3 | `failure_recognition` |
| `malformed_input` | 6 | 6 | 6 | 0 | **none** |
| `permission_denied` | 5 | 2 | 2 | 0 | **none** |
| `escalation_required` | 5 | 1 | 1 | 0 | `escalation_discipline` |
| `recovery_after_failure` | 3 | 3 | 3 | 0 | `recovery` |
| `rate_limited` | 0 | — | — | — | **none** |
| | **44** | **37** | **25** | **4** | |

### The finding in that table

**Eleven of the forty-four feed no competence dimension.** `malformed_input` and
`permission_denied` map only to `protocol_conformance` — which is excluded from the spread pool and
from the count of dimensions that could have discriminated (ADR-0052).

So a quarter of the corpus would be graded, would produce verdicts, and would move nothing about
whether the agent certifies. They are not wasted — a `malformed_input` FAIL is a real finding about
a real behaviour, and `protocol_conformance` is a real dimension — but **they do not answer the
question a certification asks.**

Worth knowing before the authoring effort is spent: six of the eleven are `malformed_input`, the
class where the five models most disagreed with the key (gemma2 and qwen2.5 wrote `REFUSE` 19–20
times of 20 where the ruling says `DECLINE`). **The class with the sharpest measured disagreement is
one of the classes whose verdict cannot affect the outcome.**

### What does move

| dimension | fed by | scenarios |
|---|---|---|
| `sequence_correctness` | `happy_path` | 13 |
| `failure_recognition` | `partial_failure` + held-out `silent_failure` | 12 + SimForge's |
| `escalation_discipline` | `escalation_required` | 5 |
| `recovery` | `recovery_after_failure` | 3 |
| `never_do_adherence` | held-out `never_do_violation` | SimForge's |

**All five competence dimensions would be exercised**, which is what ADR-0072's breadth rule asks
for and what no run has ever achieved. 33 of the 44 carry that weight.

---

## What is still missing before a verdict

1. **`situation` on the payload.** The Office's, one field, and nothing downstream works without it.
2. **The caller.** `run_scenario_pack` is declared and deliberately unbound, and ADR-0050 forbids an
   endpoint from triggering a battery — so where it is called from is a decision, not a line.
3. **The merge**, P3 — `merge_dimension_results` and `build_gate_result_request` are both ready and
   waiting for a second half to merge.
