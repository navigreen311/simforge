# ADR-0089 — The submitted half runs inside, and both halves reach the gate result

**Status:** accepted · **Decided by:** Ivan Green, 19 September 2026 · **Built (P2 item 5, P3).**
**Follows:** [ADR-0086](ADR-0086-the-runner-grades-by-transcription.md) and
[ADR-0087](ADR-0087-a-scenario-carries-the-situation.md), which left the caller a decision.

---

## The rulings

**1. Three attempts stands, at 44 scenarios.** *A pass means passed every time. If it proves too
slow, the answer is fewer scenarios or a faster model, never fewer attempts.*

**2. The submitted battery runs inside `battery_for_run`, not as a second entry point.** *Two entry
points could disagree about whether a run is gradeable, and a submitted-only run would need a
second breadth clause to catch.*

**3. The run's own content hash is used**, not the instruction set's current one. *An instruction
set re-authored mid-run must not silently change what an exam was set from.*

**4. The system context is shared** between submitted and held-out probes. *A different context
between them is a tell.*

---

## Built

`run_submitted_battery` in `battery.py`, called from inside `battery_for_run` immediately after the
held-out attempts, and both halves passed to `build_gate_result_request`.

**Ruling 1 — three attempts, weakest-wins.** `merge_submitted_attempts` uses the same
FAIL < NOT_RUN < PASS ordering the held-out side uses, because the two halves merge into one rubric
and a different rule on each would make the merged number mean neither.

It keeps **the reasons of the attempt that decided it**, not a union across attempts: a scenario
that failed once on the act and once on the claim did not fail on both in any single answer, and
reporting it that way would describe a run nobody had.

**Ruling 2 — inside.** Everything the runner needs is already in scope there: the run, the gates,
the production-settings runtime, the never-do list, and `village_ref`.

**Ruling 3 — `run.instructionContentHash`.** The same distinction `build_gate_result_request`
already draws to VOID a cert whose hashes disagree.

**Ruling 4 — one `battery_system_context`**, built once and used by both halves.

**P3.** `submitted_rubric_results` and `submitted_class_results` on the builder, which already
refuses one without the other. `merge_dimension_results` takes the worse verdict per dimension,
which matters on `failure_recognition` — the one dimension both halves report into, held-out
`silent_failure` beside submitted `partial_failure`.

`submitted_dimension_results` reuses `DIMENSION_SCENARIO_CLASS` and `_dimension_item` rather than
copying either: **a second copy of the mapping is a second thing to keep true.** It excludes
`protocol_conformance`, which is appended once from the held-out report — a submitter cannot author
a conformance verdict, and letting the submitted half report one would put a fact about answers to
held-out probes in the hands of the party forbidden to see them.

### A circular import, and what it revealed

`submitted_scoring` imported the four ACT constants from `battery`, and `battery` now imports
`submitted_scoring`. The cycle was real — and the import was **dead**: `_ACTS` was defined and never
read, because the grader compares `observed_act != key.expected_act` directly. Deleting it broke the
cycle and removed a set nothing used.

## What it changes today: **nothing, and that is correct**

The Office does not send `situation`, so every stored key is unputtable, every submitted dimension
is NOT_RUN, `is_competence_unexercised` fires and the verdict is `provisional` — exactly as before,
now for a recorded reason.

**The blocker was never the runner.** Two tests hold both sides: stored scenarios reach the outcome
and give a submitted-only dimension a verdict, and a module with none is unchanged.

## The cost, measured

[What a full exam costs](../what-a-full-exam-costs-2026-09-19.md). At **1.05 s/probe** on this card,
both halves and three attempts:

- **~2 min 52 s** for one agent across the four runnable modules
- **~5 minutes** for all three Greenstone agents, the whole venture

**Three attempts is not the expensive part** — it costs about two extra minutes per venture. The
number that would hurt is the model: llama3.1 at 3.4 s/probe makes the same sweep ~19 minutes.
Ruling 1 holds comfortably, and its own fallback is the right one if it ever stops holding.

`underwrite_deal` cannot run at all — no instruction set in SimForge, so 13 of the 44 keys have no
module to bind to.
