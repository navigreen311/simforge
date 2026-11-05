# ADR-0165 — A department is measured before real clients

**Status:** accepted · **Decided by:** Ivan Green, 2026-11-05 · **Not built.**
Supersedes, once built, the stop-gap in [ADR-0062](ADR-0062-production-settings-and-three-attempts.md)
ruling 3 (Unit B, option A). Builds on
[ADR-0132](ADR-0132-the-sweep-selects-unit-a-only.md) and
[ADR-0161](ADR-0161-the-office-posts-a-department-outcome.md).

## The question

> Department (Unit B) exams are never graded. 53 of 53 Burkham department
> runs (29 Sep - 4 Nov) ended TIMEOUT at 3 hours, 0 graded. Propose what
> must exist before real clients.

## The rulings (Ivan Green, 2026-11-05)

> 1. Real clients may start on attested Unit B only once items 1, 2 and 4
>    are built, with a fixed hand-over-exam date before the first real
>    client's grant (date set when that client is scheduled).
> 2. (a): open no Unit B run without an attestation in force.
> 3. An escalation counts for 90 days; any change of department members
>    cancels it.
> 4. Counsel review = reviewer, date and compliance library version,
>    recorded on the attestation; SimForge records, doesn't judge.
> 5. Attested certifications stop counting at Gate 9 on the cut-over date,
>    before any real client's grant.

## What was measured (5 November, read only)

SimForge, `OperationRun` where `unit = 'B'`:

| forge | runs | verdicts | started |
|---|---|---|---|
| capitalforge (Burkham) | 50 | 50 TIMEOUT | 29 Sep - 4 Nov |
| cre-forge (Greenstone) | 48 | 46 TIMEOUT, 2 PROVISIONAL | 18 Sep - 23 Oct |
| funnelforge (Burkham) | 3 | 3 TIMEOUT | 9 - 10 Oct |

- Every capitalforge run had a 180-minute window. By department: administration
  16, banking 18, operations 16.
- `DepartmentOutcomePost` has 2 rows, both `recorded`. Those are the two cre-forge
  PROVISIONALs.
- `department_context` certifications: cre-forge `provisional` 2, and one
  `revoked` voiceforge row.
- No Unit B run has ever closed PASS.

The Office:

- 85 capitalforge department submissions, over 50 SimForge refs (73 superseded),
  0 with an attestation.
- `department_attestation` has 6 rows, all cre-forge, and none records a defect.
  There are none for Burkham.
- Burkham escalations raised, received and answered: banking 2, administration 0,
  operations 0.

The Office's checklist counts 53 Burkham department runs. All 53 are here:
50 capitalforge and 3 funnelforge, every ref under `office:burkham-wickmont`.

## Why nothing grades them: by design, not by fault

A department exam has no grader. It is not that a grader fails to run.

1. **No measurement exists.** ADR-0062 ruling 3 chose option A: a named founder
   attests two flags, escalation path and compliance coupling. Option B, a real
   hand-over test, was named as the answer and not built.
   `DEPARTMENT_HANDOVER_TEST = False`, and `/api/version` publishes it.
2. **The battery refuses a department run.** `battery_for_run` returns
   `SKIP_NOT_UNIT_A` for `unit != 'A'`.
3. **The sweep does not select one.** `unscored_runs` filters to `unit = 'A'`
   (ADR-0132), because a department run only took a slot and was skipped every
   hour. ADR-0132 says it outright: *"Nothing scores a department run. That gap
   is unchanged and separate."*
4. **The only way to close one is a post.** ADR-0161 gives that post its route:
   The Office's Gate 8 sends the attestation in force to `department_outcome`.
   That calls `gate_result`, which writes the `department_context`
   certification. Gate 8 posts nothing for a department nobody has attested.
   Burkham has no attestation, so its Gate 8 opens the run, posts nothing, and
   `run_timeout_sweep` stamps TIMEOUT at :35 after 180 minutes.

So TIMEOUT on a department run does not mean the exam ran out of time. It means
no attestation arrived. The verdict does not say that.

## How it meets The Office's attestations (entries 325, 326)

- **`POST /api/attestations`** is the only writer (entry 326). Only Ivan or Ira
  can call it.
- **In simulation the best result is PROVISIONAL.** `attestation.check` refuses
  `compliance_coupling_verified = true` while the venture is in simulation
  (entry 166). It refuses `escalation_path_verified = true` without an
  escalation that was raised, received and answered for that department.
- **The verdict is held.** An attested PROVISIONAL or FAIL is held on
  `curriculum_submission.attested_verdict` while the venture's simulation
  stands (entry 325). The simulation Unit B certification is not touched.
- **Leaving simulation voids the simulation certification** (entry 167). Gate 9
  counts only `certified`. A Unit B row reaches `certified` only on an
  attestation with both flags true and no defect.

**For Burkham today:**

- With no attestation, leaving simulation leaves every department
  `never_certified` or `simulation_certification_void`. Gate 9 refuses those
  grants.
- With attestations, administration and operations could attest the escalation
  path only as false: no escalation has travelled there.
- Even at best, `certified` would mean a founder said so. ADR-0062 called that a
  stop-gap.

## What must exist before real clients

### 1. A department run says why it closed

Today a department run with nothing posted is stamped TIMEOUT, the same as a
Unit A exam the examiner failed to finish. A reader of 53 TIMEOUTs cannot tell
the two apart.

**Ruled (a): open no Unit B run without an attestation in force.** Gate 8 opens
a Unit B run only when an attestation is in force. SimForge cannot see The
Office's attestations, so the start request names the one it will post. While
`DEPARTMENT_HANDOVER_TEST` is false, SimForge's `run/start` refuses a Unit B run
that names none, with a code that names the cause (for example
`no_attestation_in_force`). The rows that cannot be told apart stop being made.

Not chosen: (b), closing such a run with its own verdict such as
`NOT_ATTESTED`. It would keep a row per attempt that carries no evidence, and
The Office would have to read the new verdict as not an answer.

### 2. An escalation path measured from a delivery, not a flag

The Office already records the fact the flag stands for:
`escalation.travelled` returns an escalation raised, received and answered, per
department. `attestation.check` reads it before it accepts a TRUE. The rule:

- **The post carries the evidence.** `department_outcome` carries the
  escalation's reference and its three timestamps. Today it carries only the
  flag.
- **SimForge checks that evidence before it accepts the flag.** The escalation is
  for this venture and department.
  - **It counts for 90 days** from when it was answered (ruled).
  - **Any change of department members cancels it** (ruled). An escalation
    answered before the members last changed does not count, however recent.

  An escalation that no longer counts leaves the flag unverified, so the
  certification is `provisional` until a new one travels.
- **The certification records the evidence.** The `department_context` row names
  the escalation it rests on, the way a Unit A row names its exam.

This measures the path. It is not derived from Unit A, which ADR-0062 rejected as
option C.

### 3. The hand-over exam (option B), for the path agents take

Item 2 shows that a person can reach the route. It does not show that the
department's agents hand over to it. The exam would:

- put escalation-required situations to each member under the department's
  composite instruction (entry 325's `module@version` set);
- grade whether each member hands over to the department's declared route rather
  than to some other route, or not at all.

Building this means:

- **Declaring the route.** The Office supplies each department's escalation route
  in the run's hand-over. SimForge holds no such field today.
- **Writing a grader.** It would be a `department_battery` with its own rubric
  kind, so no Unit A row is read by a department rule (ADR-0100).
- **Updating the selectors.** `unscored_runs` and `battery_for_run` admit Unit B
  only for that grader.
- **Flipping the flag.** `DEPARTMENT_HANDOVER_TEST` goes to true when it is
  built. `test_the_handover_test_does_not_exist` fails until then, as designed.
  Gate 9 then stops counting attested units (`attested_but_a_test_now_exists`),
  so each one has to be re-earned.
- **The cut-over date (ruled).** Attested certifications stop counting at Gate 9
  on the cut-over date, and that date falls before any real client's grant. The
  date is fixed when the first real client is scheduled. Until then, real
  clients may start on attested Unit B only once items 1, 2 and 4 are built.

### 4. Compliance coupling stays a founder's statement, with evidence named

No test can show that a compliance library was reviewed by counsel. Entry 166
already makes TRUE impossible in simulation. The rule keeps it attested and
requires the attestation to name the counsel review it rests on (ruled):

- the reviewer;
- the date of the review;
- the compliance library version reviewed.

These are recorded on the attestation. SimForge records them on the
certification and does not judge them.

## Order

1. Item 1(a), so the record stops making rows like the 53 Burkham TIMEOUTs,
   which cannot be told apart.
2. Item 2, the smallest change that turns one of the two flags into evidence.
   Burkham banking already has two travelled escalations, answered 6 and
   8 October. Under the 90-day rule they count until 4 and 6 January 2027,
   unless banking's members change first.
3. Item 4, together with Burkham leaving simulation.
4. Item 3 and the flag flip, by the cut-over date, before the first real
   client's grant.

Each is its own PR and its own ADR when built. Item 3 bumps the rubric under
ADR-0100. Items 1, 2 and 4 change the contract (`docs/contracts/department-outcome.md`)
and need a matching change in The Office.

## Until built

This ADR records the rulings. Nothing is built yet:

- No code, migration, protocol or rubric is touched.
- No run, certification or attestation is edited.
- `DEPARTMENT_HANDOVER_TEST` stays false.
