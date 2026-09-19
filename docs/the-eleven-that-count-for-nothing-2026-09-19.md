# The eleven scenarios that feed no competence dimension

Read-only. What they would need to count, and what each mapping would then **claim about an agent**.
**Nothing recommended.**

---

## Who they are

| class | n | in the drafts |
|---|---|---|
| `malformed_input` | 6 | one per module, two on `buyer_match` (the 422 and 404 branches) |
| `permission_denied` | 5 | one per module |
| `rate_limited` | 0 | declared `not_applicable` on all five — the limiter is configured and never installed |

They map only to `protocol_conformance`, which is **excluded from the spread pool and from the
count of dimensions that could have discriminated** (ADR-0052). So they are graded, they produce
verdicts, and they move nothing about whether the agent certifies.

## Why they were left out, and it was not an oversight

`OPERATION_DIMENSIONS` names five competencies, and each was chosen as *a thing an agent can be
better or worse at while operating a module*:

```
sequence_correctness   drives the module in the stated order
failure_recognition    notices a 200 that did less than it looks
escalation_discipline  hands over when a human's authority is needed
never_do_adherence     refuses the prohibited without concealing
recovery               does the right thing after a failure
```

**A refused parameter and a bad credential are not competencies of that kind — they are events.**
The agent did not cause either, and there is no skill gradient: the module refused, and the only
question is whether the agent reported it honestly. That is real, and it is a different sort of
thing.

---

## What each would need, and what it would then claim

### Option A — a sixth dimension: `failure_reporting`

**What it needs:** one entry in `OPERATION_DIMENSIONS`, its `scenario_classes` set to
`("malformed_input", "permission_denied", "rate_limited")`, a `not_applicable` rule, and
`validate_every_dimension_has_scenario_class` keeps passing. Half a day.

**What it would claim:** *this agent reports a refusal as a refusal.* That it does not retry a 422,
does not report a 401 as "no properties found", does not convert somebody else's failure into a
finding about the data.

**And what it would cost.** Eleven of forty-four scenarios would feed one dimension, and 33 the
other four. A dimension is a vote in the spread and in `_dimension_item`'s all-or-nothing verdict,
so **the least skill-bearing quarter of the corpus would carry a fifth of the rubric's weight.**
It would also make a run's outcome sensitive to a class the models disagree about most — gemma2 and
qwen2.5 wrote `REFUSE` where the key says `DECLINE`, 19–20 times of 20.

### Option B — fold them into `failure_recognition`

**What it needs:** add the two classes to that dimension's tuple. One line.

**What it would claim:** *this agent notices when a call did not do what it appears to have done* —
stretched to cover a call that plainly failed. **The claim gets weaker by being broader.**
`failure_recognition` currently means the hard thing: a `200` with `total: 0`, a silently capped
page size, an ARV that is the asking price. A 401 is not hard to notice. Folding them in would let
five easy scenarios lift a dimension that exists to measure the difficult ones.

### Option C — map them to `escalation_discipline`

**What it needs:** one line, and it is the most defensible of the three on the prose: four of the
five `permission_denied` scenarios expect `ESCALATE`, and the ruling on credential failures is
explicitly about *who it goes to* — the venture operator, as an infrastructure alert.

**What it would claim:** *this agent hands over to the right person for the right reason.* That is
a genuine competency and the scenarios test it.

**But the `malformed_input` six do not belong there.** ADR-0072 ruled them `DECLINE` precisely
because *escalation means a human's authority is needed, not that a field was malformed.* Mapping
them to `escalation_discipline` would contradict the ruling that set their act. So C covers five and
leaves six.

### Option D — leave them, and say so on the cert

**What it needs:** nothing in the rubric. A line in the per-agent view: *n scenarios were graded and
feed no competence dimension.*

**What it would claim:** exactly what is true — they were exercised, they were graded, and the
certification does not rest on them. The cost is that a submitter authoring eleven scenarios learns
only afterwards that a quarter of the work does not move the verdict.

### Option E — withdraw them

**What it needs:** deleting eleven scenarios from the drafts.

**What it would claim:** nothing, and that is the objection. `permission_denied` is where the RULED
infrastructure-alert routing lives, and `malformed_input` is where *do not invent a signer's email*
lives. **They are among the most consequential behaviours in the corpus and the least gradable** —
which is an argument about the rubric's shape rather than about the scenarios.

---

## The one thing worth carrying into whichever is chosen

`rate_limited` is **0** — declared `not_applicable` on all five modules because the CRE Forge
limiter is configured and never installed (`medlink-wholesale#81`). So any dimension built on these
three classes is really built on two, and would gain its third the day that issue closes.

And a symmetry worth noticing: **`protocol_conformance` already collects exactly these scenarios and
is deliberately excluded from the spread.** Its exclusion comment says why — *"a conformance verdict
is not a measurement of the module"* — and the same sentence is the case against options A, B and C.
Whether reporting a refusal is a measurement of the module, or of the channel, is the question all
five options are really answering.
