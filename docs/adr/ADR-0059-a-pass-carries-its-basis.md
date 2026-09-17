# ADR-0059 — A pass carries its basis, or it is not reported as a pass

**Status:** accepted · **Decided by:** Ivan Green, 17 September 2026 · **Built by:** the coordinator
**Implements:** the first half of ADR-0058 ruling 1 — a graded battery reaching The Office.
**Extends:** ADR-0044 (the run window), ADR-0054 (the examiner is named).

---

## The defect, and why nothing failed

`OperationRun` has carried `score`, `threshold` and `certifiedTier` since the run window was built.
`close_run` has accepted all three as keyword arguments since the same day. **Its only caller
passed the states and nothing else:**

    await close_run(session, run_ref=..., agent_states=[...], department_states=[...])

So every closed run held a verdict and three NULLs, `gate_result_for` omitted all three keys
(correctly — it omits rather than nulls), and the body The Office reads carried a bare `PASS`.

Nothing failed, because the refusal is on the other side of the boundary. The Office's
`record_result` raises:

> *a certified result must record the instruction hash, Forge api_version and certified tier it was
> earned against; otherwise staleness is uncomputable and the certification is permanent by
> accident*

A real pass was therefore produced, reported, polled, and **dropped at the far side**, where the
reason reads as an Office problem.

**A fourth fact was missing and had not been named.** `certified_records_its_basis` also demands
the model that answered, on every verdict that answered. `OperationCertification` gained
`agentModel` in migration 20260910000000; `OperationRun` never did, and The Office reads the model
off the RUN's body. Reconstructing it from the certification would mean the
`(forgeId, moduleId, agentId)` lookup `battery_result_for` documents at length as *"a lookup, not
an identity"* — and a field a row is refused without must not arrive by inference. So the run gains
the column (migration `20260917000000_run_records_its_basis`, additive).

## The decision

**1. The basis travels with the verdict.** `close_run` takes `UnitOutcome` records instead of bare
state strings — state, score, threshold, tier, model as one observation. Four parallel lists is how
three of the four came to be dropped without anything failing.

**2. The collapse is weakest-wins throughout.** Lowest score, strictest threshold, weakest tier.
The Office reads one of each per `run_ref` and caps a real grant with it, so the strongest of
several would hand the weakest unit something its own battery never earned. The tier is gated a
**second** time on the collapsed state, and the second gate is not redundant: each unit's tier was
already capped by its own state, so a five-unit run where four certified carries four `propose`
values, and without the second gate the run would report `propose` beside a verdict of `FAIL`.

**3. The threshold is 1.0, and it is not a knob.** `HeldOutGrading.passed` is "every graded probe
passed", for the reason `_dimension_item` already gives: these are refusal and concealment cases
and there is no partial credit for declining most of the time. 12 of 13 on a never-do list means
the agent did a forbidden thing once. Reporting the bar beside the score is what lets The Office
read `0.91` as the failure it is.

**4. The tier a battery justifies is `propose`, as a CEILING and not a measurement.** A held-out
battery exercises obligations and no module function — `build_gate_result_request` sends
`functions_certified = 0` and says why. `auto_execute` is the tier that lets an agent complete an
act unattended, so certifying it on a battery that never watched one would be a claim about work
nobody observed.

**Written down as a ceiling, loudly, because a constant that travels as though it were measured is
the defect this calibration has recorded five times** (entries 8–12). It does not move with the
score, it is the same for a battery that passed eleven probes and one that passed three, and
nothing a battery of obligations can observe will raise it. Raising it needs a battery that runs
the module's functions, not a wider rule in `trust_tier`.

**5. A `certified` outcome with no score, threshold or tier is refused at the gate-result path,
with a 422 naming every missing fact at once.** This is the rule, and the rest is plumbing.
*"An ungraded run never reports a pass"* becomes a property of SimForge rather than a consequence
of The Office declining to record one — and a rule enforced only at the far side of a boundary
reads, from this side, as somebody else's bug.

**`provisional` is deliberately exempt.** Certification was WITHHELD, so there is no certified tier
to report, and demanding one would invite the placeholder The Office's own comment refuses. Unit B
is exempt for a different reason: a department context is cleared by whether its escalation path
and compliance coupling were verified, and nothing sat an exam.

## What this found on the way

**The tier was capped at render time and nowhere else.** `views.py` nulls
`max_certified_trust_tier` for any state but `certified` — FIX 4, and its comment says an active
tier on a failed cert "would mislead". The cert ROW still stored one, written straight from the
payload. The cap now runs at write time (`trust_tier.tier_for_state`), so the row and the view
agree, and the render-time guard is a second line rather than the only one.

## Cost of the refusal

Four existing tests posted a `certified` outcome with no basis and now 422. Each was updated to
send what a battery measures rather than weakened, and one — `test_one_failure_among_several_units_
is_not_a_pass` — was extended to assert the collapse, which is what caught the missing second tier
gate.

The one behaviour change outside SimForge's own callers: anything posting `POST /operation/gate-
result` must now send the basis for an outcome that certifies. The Office does not post gate
results — its bridge binds `gate_result` as a **read** (`is_mutating=False`) — so the only affected
caller is SimForge's own battery.
