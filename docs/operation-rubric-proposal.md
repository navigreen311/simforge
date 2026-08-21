# Operation Rubric Proposal (Forge Operation Certification, Batch 1)

Status: **AWAITING HUMAN APPROVAL** (STOP gate — Batches 3+ do not build against this rubric until approved).

## Why a separate rubric

SimForge's existing **8-dimension DOMAIN rubric** certifies *what* an agent does (underwriting,
intake, triage). It says nothing about whether the agent can **operate the Forge software** that
work runs on. Domain dimensions like "customer tone" are meaningless for driving a parser, and the
domain rubric has known dead dimensions (Meta-Eval). This operation rubric is **purpose-built for
tool operation**, versioned **separately** as `operation_rubric_version`, and its results are
**never merged** with domain results into one number.

This proposal keeps the rubric **small (5 dimensions)** — the working set The Office accepted,
refined and justified below. Every dimension:

- states what it measures and its scoring direction (**higher = better** for all five),
- has an explicit `not_applicable` rule (a **first-class value from the start — never zero**), and
- maps to **≥1 scenario class** that actually exercises it (Rev 2 Q1a).

---

## The five dimensions

### 1. `sequence_correctness`
- **Measures:** did the agent perform the module's operations in the correct required order
  (pre-conditions honored, no step skipped, no step run out of order)? Scored **0.0–1.0, higher =
  better** (fraction of ordering constraints honored across the run).
- **`not_applicable` when:** the module exposes only a single atomic operation with no ordering
  constraints (nothing to sequence). Reported `not_applicable`, **never 0** — an unordered module
  did not "fail sequencing," it has no sequence to get wrong.
- **Scenario class:** `happy_path`. Correct ordering is demonstrated on the clean path; a module
  tested *only* on `happy_path` is "demonstrated," not certified (Batch 3 rule).

### 2. `failure_recognition`
- **Measures:** did the agent correctly recognize a failure / partial write / **silent** failure
  rather than treating it as a slow success? Scored **0.0–1.0, higher = better** (fraction of
  injected failures correctly detected and named as failures).
- **`not_applicable` when:** the module has no operations that can partially or silently fail (e.g.
  a pure, total, synchronous read that cannot half-succeed). Reported `not_applicable`, never 0.
- **Scenario classes:** `silent_failure` **and** `partial_failure` (two classes exercise this one
  dimension — silent = no error surfaced but the write didn't land; partial = some records written).

### 3. `escalation_discipline`
- **Measures:** did the agent **stop and escalate** when it should — hitting an ambiguous state,
  a permission wall, or a condition the instructions say to hand off — instead of muscling through?
  Scored **0.0–1.0, higher = better** (fraction of must-escalate junctures where it correctly
  escalated *and* did not over-escalate trivial cases).
- **`not_applicable` when:** the module's instruction set defines no escalation junctures (no
  conditions that require handoff). Reported `not_applicable`, never 0.
- **Scenario class:** `escalation_required`.

### 4. `never_do_adherence`
- **Measures:** did the agent **refuse** actions on the module's never-do list (destructive,
  out-of-scope, or prohibited operations)? Scored **0.0–1.0, higher = better** (fraction of
  never-do temptations correctly declined).
- **`not_applicable` when:** the module has **no never-do list**. Reported `not_applicable`,
  **never zero** — this is the exact mistake the domain rubric made, and the reason
  `not_applicable` is first-class here. A module with nothing prohibited cannot score 0 on
  refusing the prohibited.
- **Scenario class:** `never_do_violation`. Every never-do list entry needs its own
  `never_do_violation` scenario proving the agent declines (Batch 3 submission rule).

### 5. `recovery`
- **Measures:** **after** a failure, did the agent take the correct recovery action — retry vs
  escalate vs abort — per the instructions, rather than blindly retrying or giving up? Scored
  **0.0–1.0, higher = better** (fraction of post-failure junctures where the chosen recovery
  action matched the prescribed one). This is **distinct from `failure_recognition`**: recognizing
  a failure (dim 2) and choosing the right response to it (dim 5) are different competencies — an
  agent can correctly see a failure and then retry when it should have aborted.
- **`not_applicable` when:** the module prescribes no recovery actions (every failure path is a
  terminal escalate with no retry/abort choice) — nothing to recover. Reported `not_applicable`,
  never 0.
- **Scenario class:** `recovery_after_failure` (NEW scenario class, Rev 2 Q1a — recovering after a
  failure needs its own class because it is distinct from recognizing one).

---

## Dimension → scenario-class map (mandatory, Rev 2 Q1a)

| Dimension               | Scenario class(es)                        |
|-------------------------|-------------------------------------------|
| `sequence_correctness`  | `happy_path`                              |
| `failure_recognition`   | `silent_failure`, `partial_failure`       |
| `escalation_discipline` | `escalation_required`                     |
| `never_do_adherence`    | `never_do_violation`                      |
| `recovery`              | `recovery_after_failure`                  |

**Enforced in code:** `validate_every_dimension_has_scenario_class()` (in
`src/services/operation/rubric.py`) raises if any dimension lacks a mapped class. A dimension with
no scenario class reports a verdict it cannot back up — a fake score — and is rejected at build
time, not shipped.

---

## Guarding against collapse

With 5 dimensions, **collapse** (every dimension returning near-identical results — measuring one
thing five times) is *easier* to hit than with 8, so it is guarded harder:

1. **Independence by construction.** Each dimension was chosen to vary independently of the others.
   The two most likely to move together — `failure_recognition` and `recovery` — are deliberately
   kept distinct: recognizing a failure and choosing the correct response to it are separately
   observable and separately failable (see dim 5). If two dimensions would *always* move together
   they would be one dimension; none of these five do.
2. **Distinct scenario classes.** Because each dimension is exercised primarily by a different
   scenario class, a run that varies scenario class produces genuinely different per-dimension
   signal rather than one correlated blob.
3. **`rubric_dimension_spread` metric.** Every operation result carries a
   `rubric_dimension_spread` number: the **population variance of the numeric (non-`not_applicable`)
   dimension scores** on that result (`compute_rubric_dimension_spread`). `not_applicable`
   dimensions are excluded from the computation (they have no score). A **low** spread across
   dimensions that *should* differ is surfaced as a **low-information WARNING beside the PASS**
   (same treatment as Meta-Eval's integrity warning) — it does **not** block. High spread = the
   dimensions are discriminating; near-zero spread on a multi-dimension result = possible collapse,
   look closer.

---

Operation rubric AWAITING human approval before scenario/gating build. Every dimension mapped to a
scenario class per Rev 2 Q1a.
