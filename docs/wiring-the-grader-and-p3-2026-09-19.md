# Wiring the grader in (item 5), and P3 (item 6)

Read-only. What the caller looks like and where it belongs — ADR-0086 left that a **decision**, and
this is the decision laid out rather than taken.

---

## What already exists

```
battery_for_run(session, run_ref, runtime)          the held-out half, end to end
  ├─ check_agent_identity / check_examiner          gates
  ├─ module_never_do_list -> author_for_module      SimForge authors its own probes
  ├─ run_module_battery x EXAM_ATTEMPTS             three attempts, weakest wins
  └─ build_gate_result_request(report, run, ...)    ready for BOTH halves already

submitted_keys_for(...)      the keys, in authored order
probe_for(key)               the situation, verbatim
grade_submitted(key, answer) act, subject, claim exact; caveat by presence
merge_dimension_results(a,b) worse verdict per dimension
```

**`build_gate_result_request` already takes `submitted_rubric_results` and
`submitted_class_results`, and refuses one without the other.** P3 was built in advance of the
thing that needs it.

---

## Item 5 — the caller, exactly

It is a sibling of `run_module_battery`, not a change inside it. Roughly forty lines:

```python
async def run_submitted_battery(
    session, *, run, runtime, seed: int = 0
) -> tuple[tuple[ScenarioVerdict, ...], tuple[SubmittedKey, ...]]:
    keys = await submitted_keys_for(
        session,
        forge_id=run.forgeId,
        module_id=run.moduleId,
        content_hash=run.instructionContentHash,   # the hash the RUN executed against
    )
    context = battery_system_context(run.moduleId, never_do)   # identical to the held-out half
    answers: dict[str, object | None] = {}
    for key in keys:
        probe = probe_for(key)
        if probe is None:
            continue                      # no situation -> NOT_RUN, by its own named reason
        raw = await runtime.turn(
            village_ref, [{"role": "scenario", "content": probe}], seed, extra_system=context
        )
        answers[key.ref] = parse_answer(raw.content)
    return grade_submitted_module(keys, answers), tuple(keys)
```

Four details that are decisions rather than typing:

**The content hash must be the run's, not the instruction set's current one.** `battery_for_run`
already makes that distinction for the held-out half — a set re-authored mid-run VOIDs the certs —
and the keys must come from the same submission the run was opened against.

**`battery_system_context` is shared, and has to be.** The submitted probe and the held-out probe
must be indistinguishable in everything but the situation. A different context is a tell.

**Three attempts, or one?** ADR-0062 rules three at production settings with distinct seeds, any
failing attempt failing the exam. It says "the exam", and a submitted scenario is part of the same
exam — so three, and `ExamReport.of` already merges weakest-wins. **Worth confirming rather than
assuming**: it triples the call count on a 44-scenario corpus.

**Where the verdicts become dimensions.** `grade_submitted_module` returns per-scenario verdicts;
`_dimension_item` turns verdicts into a rubric row. That function is in `held_out_scoring` and is
class-agnostic, so it is reused rather than rewritten — the mapping is
`DIMENSION_SCENARIO_CLASS`, already the single source.

## Where it belongs — and this is the real question

ADR-0050: **no endpoint may trigger a battery.** The held-out corpus lives in the process, and a
route that could start one is a route that could be made to reveal it. So the caller is
process-side, and there are exactly two process-side callers today:

| | | |
|---|---|---|
| **`battery_for_run`** | called by `submit_battery_result`, itself called by the scheduler | **the natural home** |
| **the scheduler's `battery_sweep`** | hourly, `triggerable=False` | calls the above |

**The recommendation-free reading:** `run_submitted_battery` is called *from inside*
`battery_for_run`, immediately after the held-out attempts, because that function already holds
everything it needs — the run, the gates, the production-settings runtime, the never-do list — and
because two entry points would mean two places that could disagree about whether a run is
gradeable.

The alternative is a separate `submit_scenario_pack_result` beside `submit_battery_result`, which
would let a submitted battery run without a held-out one. That is a real option and it has a cost:
**a run producing only submitted results would be the mirror image of today's discipline-only run**,
and ADR-0072's breadth rule would have to grow a second clause to catch it.

**And `run_scenario_pack` is the name already declared for this** — in the Burkham Pack's
`modules_expected`, deliberately unbound, with V32 failing on it. Binding it is the visible half of
this decision; the invisible half is whether it becomes a second entry point or an internal step.

---

## Item 6 — P3, the merge

**Genuinely small, because the hard part was built first.**

```python
report = ExamReport.of(*attempts)                      # held-out, unchanged
submitted, keys = await run_submitted_battery(...)     # item 5
built = build_gate_result_request(
    report=report,
    run=run,
    instruction_set=instruction_set,
    agent_model=...,
    model_identity=...,
    submitted_rubric_results=[_dimension_item(d, vs) for d, vs in by_dimension(submitted)],
    submitted_class_results=[{"scenario_class": v.scenario_class, "verdict": v.verdict}
                             for v in submitted],
)
```

`merge_dimension_results` then takes the **worse** verdict per dimension, which matters on
`failure_recognition` — the only dimension both halves report into (`silent_failure` held out,
`partial_failure` submitted). A held-out FAIL must never be softened by a submitted PASS, and that
direction is already asserted.

**What P3 unlocks, stated plainly:** with both halves present, `is_competence_unexercised` stops
firing, all five dimensions carry a verdict, and `certified` becomes reachable for the first time —
at the `propose` ceiling, per ADR-0069 ruling 4.

**One hour, maybe two.** It is the only item on the list that is an edit rather than a decision.

---

## What still gates a real verdict, after both

1. **The Office sends `situation`** — without it every submitted key is `NOT_RUN` and the breadth
   rule holds the run at `provisional`. One field, their side.
2. **`underwrite_deal` has no instruction set in SimForge** — 13 of the 44 keys have no module to
   bind to.
3. **`SCHEDULER_ENABLED`** — off, and nothing but the scheduler can start a battery.
