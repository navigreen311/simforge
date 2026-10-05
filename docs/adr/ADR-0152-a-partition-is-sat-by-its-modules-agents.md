# ADR-0152 — A partition is sat by its modules' agents

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-05 · **Built.**
Narrows ADR-0110 (scope, R3 and the NOT_RUN table).

## The ruling

> Approved: the module-scope roster fix now (new ADR narrowing ADR-0110,
> shared roster function, venture_verdict counts only rostered agents, the
> test). Backlog the grant-backed roster from The Office.

*Measured (2026-10-05, partition `01M46DFTT7DMEGFVA4ZQ4KCX6D`,
burkham-wickmont):*

- *Seven agents sat it, 3/3 PASS each, no slips.*
- *kellan_jovaris read NOT_RUN. His only runs were on `submit_application`,
  which the partition does not cover. His Burkham grant was retired on
  Oct 4.*
- *Gate 9.5 read NOT_RUN on that one row.*

## What was wrong

ADR-0110 took the roster from every Unit-A run on the forge for the venture.
There was no time bound, no grant and no module check. An agent with no
module in scope was rostered, put nothing, and recorded NOT_RUN. NOT_RUN is
never a pass, so one such agent held the gate for the whole venture.

## The rule now

- **The roster is one function**, `partition_roster`. It returns agents with
  at least one run on a module the partition covers. Each agent carries only
  those modules.
- **The scope** is the key set of the partition's `instructionHashes`,
  recorded at authoring (ADR-0125, ADR-0129). It equals the modules that
  have scenarios.
- **The grader** puts the partition to the roster only. An agent off the
  roster gets no row.
- **The verdict** (`venture_verdict`) reads rows of rostered agents only.
- **Rows are not deleted.** Verdicts are append-only. An old NOT_RUN for an
  agent now off the roster stays in the table and is not read.
- **No recorded scope** (a partition from before ADR-0125) keeps the
  ADR-0110 roster. Such a partition is never graded, and its verdict reads
  as it always did.

ADR-0110's "no module in scope ⇒ NOT_RUN" no longer happens. Its other
NOT_RUN causes stand: the Village cannot name the agent, or a module has
no current never-do list.

## What this does not do

- **It is not a grant check.** SimForge holds no grants. A retired agent
  whose runs touched a module in the partition is still rostered, and can
  still hold the gate.
- The grant-backed roster needs The Office to send its live grants. It is
  on the backlog.

## Isolation

`partition_roster` reads `OperationRun` and nothing else. It never names
`HeldOutPartitionScenario`, so the verdict service may import it. The
router import-graph guard (`test_no_router_can_reach_the_scenarios`) is
unchanged and passes.

## Versions

- **None.** Protocol 14.0.0 and rubric 0.13.0 are unchanged. No grading
  changes.
- **No migration.**

## Tests

`test_an_out_of_scope_agent_does_not_sit.py`:

- The roster holds only agents on a partition module. Control: no scope
  keeps the old roster.
- The sweep writes no row for an out-of-scope agent; the gate reads PASS.
- An old NOT_RUN row for an out-of-scope agent stays and no longer holds
  the gate.
- Control: an in-scope agent's FAIL still holds it.

The two fix-dependent tests fail on the code before this change.
`test_a_moved_partition_answers_not_run.py` now seeds a run for each agent
it grades.
