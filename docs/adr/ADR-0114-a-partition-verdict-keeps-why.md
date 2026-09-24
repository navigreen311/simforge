# ADR-0114 — A partition verdict keeps why, on SimForge's side only

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-24 · **Built.**

---

## The ruling

> A partition verdict keeps why, on SimForge's side only. Per-scenario
> outcome, module, class and failure-mode code, retained with the verdict.
> Never scenario content, and never sent to The Office - the endpoint's
> four keys are unchanged.
>
> *Measured: three agents failed 141 scenarios each and nothing records
> which module, class or mode, so a verdict cannot be acted on.*

This amends ADR-0110, which kept whether and discarded why inside
SimForge as well as at the boundary.

## What was measured first (read-only, 24 September)

The question: each agent took 70-80 s for up to 141 probes, about 0.5 s
each on local phi4. How many probes got a model answer?

**It cannot be answered from anything recorded.**

- `put_partition` graded every probe, then folded the results to one
  verdict. The per-probe results were discarded.
- `HeldOutPartitionVerdict` has no reason column. The log holds one
  `partition_agent_graded` line per agent, verdict only.
- `LLM_CACHE_MODE` is `off`, so no response was written to disk.
- Ollama's own `server.log` stops on 20 September.

What the code does establish:

- **An empty or unparseable answer is a FAIL**, not NOT_RUN. It is a
  protocol violation (`answered_with_no_act_line`, ...).
- **Only a provider exception is NOT_RUN.**
- **Any single FAIL fails the agent** (`agent_verdict`). One bad answer
  in 141 is enough.
- So the three FAILs prove at least one probe per agent came back and was
  graded. They cannot show how many were real answers.

Checked and ruled out: prompt truncation. Ollama serves phi4 at
`context_length: 4096`, and the largest probe plus operating context is
about 2,200 tokens.

## Built

`HeldOutPartitionOutcome`: one row per probe, append-only, written in the
same commit as the verdict it stands behind.

| Column | Holds |
|---|---|
| `verdictId` | the FAIL / PASS / TIMEOUT / NOT_RUN row |
| `scenarioId` | a reference to the scenario row, never its content |
| `moduleId`, `scenarioClass` | where it failed |
| `outcome` | PASS, FAIL or NOT_RUN |
| `failureModes` | declared `REASON_*` codes only; empty on PASS |
| `answerState` | `answered`, `empty`, `unparseable`, `provider_error` |
| `tokensOutput`, `latencyMs` | as the provider reported them |

- `answerState` is the measurement the 04:50 run could not make: a FAIL
  on an empty answer now says so.
- A timeout keeps the probes graded before it, under the TIMEOUT row.
- `scripts/partition_outcomes.py --partition <id>` summarises per agent:
  answer states, outcomes by module and class, and failure-mode counts.
  It prints no probe, answer or scenario id.

## The boundary, unchanged

- No route reads the table. The router import-graph test now also refuses
  any request-reachable module that names `HeldOutPartitionOutcome`.
- The verdict endpoint's four keys are unchanged. A test puts outcomes
  behind a FAIL and asserts that no module, mode or answer state appears
  in The Office's response.
- No row carries a probe or an answer. A test searches every column of
  every row for each line of every probe and every answer.

## Tested

`tests/integration/test_a_partition_verdict_keeps_why.py`, 13 tests,
driven through the scheduler's own path, all read from a fresh session.

- A failing agent: one row per probe, all behind the final verdict,
  modes from the declared set.
- Empty, whitespace and prose answers are each named, and each is a FAIL.
- A mixed sitting counts exactly.
- A provider failure is kept as NOT_RUN / `provider_error`.
- A timeout keeps the two probes graded before it.
- Mutation: dropping the outcome write fails 8 of 13.
- Both schemas carry the table: Prisma and the migration are read.

## What this does not do

- It does not re-grade the 04:50 sitting. Those FAILs stay without a why.
  The next sitting after a re-seal records one.
- It does not change the fold. One FAIL still fails the agent.
- It does not apply the migration to the dev DB. That waits for merge.
