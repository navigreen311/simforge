# ADR-0090 — Two conditions, two reasons

**Status:** accepted · **Decided by:** Ivan Green, 19 September 2026 · **Built.**

---

## The ruling

**`SKIP_NO_MODULE` is returned from two different conditions. Give them separate reasons, so a
reader is sent to the right place.**

## What shared it

`battery_for_run` returned `the_run_declares_no_module_or_agent` from two guards:

| guard | what is actually wrong | who fixes it |
|---|---|---|
| `not run.moduleId or not run.agentId` | the hand-over is incomplete | whoever opened the run |
| `instruction_set is None` | SimForge holds no curriculum for that module | whoever submits it |

On the second branch **the reason's own value is false.** The run declares both. A reader following
it went to `OperationRunStartRequest` and found a payload that was correct.

## Built

- `SKIP_NO_INSTRUCTION_SET = "no_instruction_set_for_this_forge_and_module"`, beside the old one.
- Both sites now log: `battery_skipped_incomplete_run` with `missing=[...]`, and
  `battery_skipped_no_instruction_set` with the forge and module.

**The first guard was not split further.** Module and agent are both fixed in the same place, so
two reasons would send a reader to the same file twice. The log names which field is absent.

## The branch was unreachable, and finding that out is the point

Splitting the constant surfaced something the shared name had been covering.

`module_never_do_list` reads the never-do list **off the instruction sets.** No instruction set
means an empty list — so the never-do guard, which ran first, returned on every input that could
have reached the instruction-set guard. `instruction_set is None` was dead.

So the guards are now **ordered lookup-first**, and each reason is true of the state that returns
it:

| state | reason |
|---|---|
| nothing submitted for this module at all | `no_instruction_set_for_this_forge_and_module` |
| a submission that declared nothing to hold out | `the_module_declares_no_never_do_list` |

This changes behaviour for one case: a module with zero instruction sets now reports the first
rather than the second. That is the correction, not a side effect.

### The cost is in our own record

Calibration entry, hand-diagnosing the September batch:

> **`submit_application` has zero rows in SimForge.** So the skip is `SKIP_NO_MODULE`, not
> `SKIP_NO_NEVER_DO` — the module is unknown, not known-and-empty.

**That prediction was wrong.** Zero rows meant an empty never-do list, and the never-do branch
returned first, so the skip was `SKIP_NO_NEVER_DO` — the reason the entry ruled out.

The distinction it drew is exactly right. The code could not make it, and one constant standing for
two conditions is why nobody could tell. Today both halves of that sentence are true statements
about what the code does.

## Tested

Three tests, in `test_operation_battery_run.py`:

1. a run opened with no module → `SKIP_NO_MODULE`
2. a run naming module and agent, with no instruction set → `SKIP_NO_INSTRUCTION_SET`
3. **the pair, side by side** — known-and-empty against nothing-submitted, asserting they differ.
   Test 3 fails on the old ordering; test 2 could not have been written at all.

## Scope

A skip posts no outcome, so no skip reason crosses to The Office. These reasons are read by
operators: `SweepOutcome.skipped` and the `battery_sweep_skipped` log. `BatterySkipped` carries
only `run_ref` and `reason`, which is why the reason has to be the thing that discriminates.

Suite: **1,099 pass, 2 skip.** `SCHEDULER_ENABLED` stays off.
