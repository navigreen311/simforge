# ADR-0110 — The sealed partition is put to the venture's agents, and only whether is kept

**Status:** accepted · **Decided under:** ADR-0108 R1–R5 · **Built.**

---

## The ruling

> A sealed partition is put to each of the venture's agents through the
> battery's own answer path. One verdict row per agent: PASS only if every
> scenario passed. No reason is kept anywhere. Nothing becomes training signal.

## Who the venture's agents are — measured

**The venture reaches SimForge in one place: segment 2 of the run ref.**
The Office's `mint_run_ref` builds
`office:{venture_id}:{forge_id}:{module}@{agent8}:...`.
Nothing in the operation path has a venture column (ADR-0058).

Measured on the dev database, 2026-09-23, read-only:

- 47 `OperationRun` rows. Every Unit-A row with an agent is Office-minted
  and names its venture in segment 2 (all `greenstone`, all `cre-forge`).
- Three agents on `cre-forge`: `victor_serath`, `seraphine_valek`,
  `ronan_valek`. Each operates one or two modules.
- Older rows carry the Village ref in `agentId` and no `villageAgentRef`.
  Newer rows carry The Office's uuid in `agentId` and the Village ref in
  `villageAgentRef`. The same agent appears under two `agentId`s.
- The `Venture` registry cannot select agents. `greenstone.internalForges`
  is `['funnelforge']`, yet every greenstone run is on `cre-forge`.

**So the rule is:** the venture's agents on the partition's forge are the
distinct Village refs (`villageAgentRef`, else `agentId` — ADR-0083) on
Unit-A runs whose `forgeId` is the partition's and whose run-ref venture
is the partition's. Each agent carries the modules it has runs on.

`agentId` on a verdict row is that Village ref: the id that was asked.
It collapses the two ids one agent has had into one.

## Scope — R3

An agent is put the partition's scenarios for the modules it operates.
Each module's probes go under its forge's **current** instruction set:
the newest `ForgeInstructionSet` for (forge, module). Its never-do list
numbers the rules an agent cites; its sections are shown (ADR-0107).

## What the agent sees

`held_out_scoring.deliver(scenario)` — `Probe(module_id, prompt)` — under
`battery_system_context` and `RESPONSE_PROTOCOL`, byte for byte what the
ordinary battery sends. `parse_answer` and `observe_answer` read the answer;
`grade_scenario` grades it. A partition probe is indistinguishable in shape
from an ordinary one.

## The verdicts

| Verdict | When |
|---|---|
| `IN_PROGRESS` | committed before the first probe is put |
| `PASS` | every scenario passed (`HELD_OUT_PASS_THRESHOLD` = 1.0) |
| `FAIL` | any scenario failed, including a protocol violation (ADR-0063) |
| `NOT_RUN` | any probe never put, or nothing could be put: no module in scope, the Village cannot name the agent, no current never-do list |
| `TIMEOUT` | one agent's grading exceeded `PARTITION_AGENT_BUDGET_SECONDS` (1800), or an `IN_PROGRESS` older than that had no successor |

- FAIL outranks NOT_RUN. NOT_RUN is never a pass (ADR-0106).
- `partitionDigest` is the partition's `contentDigest` at grading time.
- `instructionContentHash` is the one set's hash, or `set:sha256:` over
  sorted `module=hash` pairs when an agent spans modules.
- Append-only. `decidedAt` is strictly increasing per agent.

**Due** means: no verdict yet, or NOT_RUN / TIMEOUT last. PASS and FAIL
settle until the partition is re-sealed (a new id, a new digest).
A NOT_RUN found before anything is put is written only if the last verdict
was not already NOT_RUN, so an hourly pass does not grow the table.

## Whether, never why

`ScenarioVerdict.reasons` live for one agent's grading and are dropped.
No column, log line or job return carries a reason, a count of failures,
a module or a scenario. The job returns counts of partitions, agents put
and rows written — and a test asserts no verdict word is in it.

## Nothing becomes training signal

The grader writes `HeldOutPartitionVerdict` and nothing else.
`test_partition_sweep` counts `OperationCertification`, `OperationRun`,
`OperationScenarioSubmission`, `ForgeInstructionSet`, `TrainingProposal`
and `Scorecard` before and after a graded pass.

## ADR-0050

`partition_sweep` is scheduler-only. A request-path call — the trigger
route hands the job a session — is refused inside the job before anything
is read. `CadenceJob.triggerable=False` is the right flag and is not set:
`test_cadence` pins the set of non-triggerable jobs to `{battery_sweep}`,
a file outside this build. Escalated (`PARALLEL_BUILD_ESCALATION_G95B.md`).

## Built

- `services/operation/partition_grading.py` — selection, putting, grading, rows.
- `workers/partition_sweep.py` — the pass, its lock, the examiner check.
- `jobs.partition_sweep` and its registry entry: hourly at :50.
- `tests/unit/test_partition_grading.py`, `tests/integration/test_partition_sweep.py`
  — the job driven through `run_scheduled`, rows read from `fresh_session`,
  and a negative control where the job reports work and writes nothing.

## What this does not do

- It does not author or seal a partition (ADR-0109).
- It does not answer The Office (ADR-0111).
- It does not add a venture column anywhere. The run ref is read as it is.
- It does not re-grade a PASS or FAIL on the same seal.
