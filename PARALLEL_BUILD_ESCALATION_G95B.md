# Escalation — Gate 9.5 grading (Session B, ADR-0110)

## 1. `partition_sweep` should be `triggerable=False`

**Needed:** one line in `apps/api/tests/integration/test_cadence.py`,
`test_every_other_job_is_still_triggerable`:

    assert {j.name for j in JOBS if not j.triggerable} == {"battery_sweep", "partition_sweep"}

plus `triggerable=False` on the `partition_sweep` entry in `registry.py`.

**Why not done:** the test file is outside this build's file set.

**What holds meanwhile:** `jobs.partition_sweep` refuses any call that
hands it a session (the trigger route's path) before it reads anything.
`test_the_trigger_route_cannot_put_the_partition` asserts no probe is put
and no row written. The route answers 200 with a named skip, not 403.

## 2. One entry outside the named files

`apps/api/src/services/cadence/jobs.py` — one function, `partition_sweep`.
`run_scheduled` calls `jobs.<name>()`, so a job must live there.
