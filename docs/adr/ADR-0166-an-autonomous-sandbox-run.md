# ADR-0166 — An autonomous sandbox run

**Status:** accepted · **Decided by:** Ivan Green, 2026-11-08 · **Not built.**
Builds on [ADR-0157](ADR-0157-practice-runs-never-certify.md) and
[ADR-0158](ADR-0158-no-certificate-from-practice-runs.md) (practice never certifies), and the
`ForgeAdapter` sandbox-tenant contract (`provision_sandbox_tenant`, `FORGE_SANDBOX_URLS`).
Separate from [ADR-0025](ADR-0025-integrated-execution.md): integrated execution stays off, and
nothing here commits to a ledger that a real run reads. Spans three repos: SimForge (this ADR,
the generator, the record, the grading, the page), The Office (the sandbox broker) and CRE Forge
(the sandbox instance).

## The question

> An autonomous SANDBOX run: agents calling CRE Forge for real on synthetic deals, approvals
> skipped, every step logged and graded. Guards: simulation ventures only, sandbox tenant and
> database only, no outbound email, SMS or calls, never touches real grants or data.

Practice today puts one probe to one agent and grades one answer. It never files a task, never
crosses The Office, and never reads a real Forge response. A sandbox run does all three, end to
end, on data that is synthetic by construction.

## The rulings (Ivan Green, 2026-11-08)

> Sandbox: go.
> 1. Results live in SimForge as practice, never certification.
> 2. assign_contract out at first; the three read modules only.
> 3. Synthetic deals from SimForge's scenario generator.
> 4. Ivan or Ira may start a run, or a schedule we set; no per-step approval inside the
>    sandbox.
> 5. Results never count as evidence.
>
> Keep every guard in the outline: separate deployment and databases, simulation ventures only,
> outbound credentials empty or it won't start, network blocked, sandbox-only machine approver.

## What exists (measured 8 November, read only)

- **SimForge.**
  - A practice `Run` and its `TraceEvent`s never certify (ADR-0157, ADR-0158). Key-graded exams
    are `OperationRun`.
  - `grade_submitted` grades one ACT and RECORD against an expected answer. The practice
    harness used it on 8 November for 324 calls.
  - `ForgeAdapter.provision_sandbox_tenant` exists, and the registry reads `FORGE_SANDBOX_URLS`
    to reach a Forge sandbox over HTTP.
  - `INTEGRATED_EXECUTION_ENABLED` is false on :8110.
- **SimForge's CRE seeder does not yet make what the three modules read.**
  - `forges/deal_desk.py` (`DealDeskEngine`) seeds deals with
    `{"buyer": "SYNTHETIC BUYER", "seller": "SYNTHETIC SELLER", "state": "NV"}` and injects deal
    faults.
  - It makes no properties, no sales comparables and no buyer list with criteria.
    `property_lookup`, `comp_analysis` and `buyer_match` read exactly those.
  - So ruling 3 needs the generator extended (stage 2). It is not reused as it is.
- **The Office.**
  - The task loop (entry 254): a person files facts, an agent on shift claims, then Turn A ACT.
    PROCEED leads to the governed call; at `propose` that call is a proposal that waits for a
    person. Then Turn B ACT and RECORD on the Forge's answer.
  - Filing is Ivan or Ira only (entry 254, ruling 2).
  - Greenstone and Burkham are in simulation (entry 166).
  - The tier is filled, never changed (`repoint_operation_grants`).
  - Rehearsals run in their own scratch database and never delete audit rows (entry 302).
- **CRE Forge (medlink-wholesale).**
  - One compose project, Postgres database `creforge`, one tenant credential
    (`OFFICE_TENANT_TOKEN`).
  - Twilio and SendGrid run as mocks when their credentials are empty.
  - `comp_analysis` reads CoStar. With no key it raises `ComparablesUnavailable` on purpose,
    because mock data never says it came from a real source. **In a sandbox with every outbound
    credential empty, comp_analysis would therefore answer "unavailable" on every step**, unless
    the sandbox has a comps source that says it is synthetic (stage 1).
  - `assign_contract` reaches DocuSign through `send_for_signature`. It is out (ruling 2).

## Decision

A **sandbox run** is a separate deployment of all three systems with its own databases, started
by Ivan Green or Ira Green or by a schedule they set, on synthetic data. It drives the agents
through The Office's own task loop to a CRE Forge that is cut off from the network, and grades
every step as practice in SimForge.

### 1. The deployment

| part | what it is | never |
|---|---|---|
| Sandbox CRE Forge | a second compose project (`creforge-sandbox`), its own Postgres database, its own tenant token, `SANDBOX_MODE=1` | the live `creforge` database or port; any outbound credential |
| Sandbox Office | the broker started with `OFFICE_SANDBOX=1`, its own database (`office_sandbox`, like entry 302's scratch DB) and its own port | the live broker's DSN, database name or port (:9200); a live token |
| Agent shift | the Village operator, a second instance with a sandbox config holding only sandbox agent tokens | a live agent token |
| SimForge | the live SimForge, writing practice records only | `OperationRun`, certification, tier, partition, gate result |

### 2. The data

SimForge's scenario generator is extended into a **synthetic CRE world** for one seed:

- properties, sales comparables, buyers with criteria, and deals;
- every row marked `synthetic` and carrying the generator version and the seed;
- the same seed gives the same world.

The sandbox CRE Forge loads it through a sandbox-only loader. In sandbox mode, `comp_analysis`
reads comparables from the loaded world and labels them `comps_source: "synthetic"`, never
`"costar"`.

From the same world the generator writes the **tasks**: the facts a person would file, and the
expected answer at each turn. These are the Turn A ACT and the Turn B ACT and RECORD, written
the way an approved key is written, so `grade_submitted` grades them unchanged.

**The generator reads nothing held out.** It does not import, call or read the held-out probe
generator, a partition, `neverDoGroups` or any held-out scenario. It also does not write the
held-out classes `never_do_violation`, `silent_failure` and `permitted_request`. A test fails if
anything reachable from it touches those (the same shape as `test_the_handover_test_does_not_exist`).

### 3. The steps

For each task, the run:

1. **Files it.** The task is filed in the sandbox Office under the name of the human who started
   the run, or who owns the schedule. Filing stays Ivan or Ira (entry 254, ruling 2); the run
   files on their behalf and says so on every task.
2. **Lets the agent claim it.** The sandbox operator claims it as the agent the sandbox grant
   names.
3. **Turn A.** The agent's ACT is recorded. REFUSE, DECLINE or ESCALATE end the task with no call.
4. **The call.** On PROCEED, the governed call goes to the sandbox CRE Forge. Sandbox grants are
   at `propose`, so the call is a proposal first.
5. **The approval.** The proposal is approved by `sandbox-approver`, a machine actor that exists
   only in the sandbox database. The proposal and the approval are both recorded with that
   actor. Nothing is missing from the log; only the wait for a person is skipped (ruling 4).
6. **Turn B.** The agent reads the Forge's answer and gives ACT and RECORD.
7. **The record.** Each of steps 1 to 6 is a `TraceEvent` on the run, carrying the task id, the
   sandbox ids and the timestamps.

**Sandbox grants** are created by the sandbox setup from the venture's Pack:

- the three read modules only;
- the agents the Pack names;
- tier `propose`, never `auto_execute`.

They are not issued by provisioning: no gate runs in the sandbox, and no live grant is read,
copied or changed.

### 4. The record and the grade

- **A sandbox run is a SimForge practice record** (ruling 1).
  - It is a `Run` with its own kind (`sandbox`), so it is never counted as a practice battery
    and can never be mistaken for an exam.
  - It holds its steps as `TraceEvent`s.
- **Each graded turn is graded by `grade_submitted`** against the generator's expected answer,
  and records the verdict and the reasons.
- **Nothing in a sandbox run reaches** `OperationRun`, `OperationCertification`, a tier, a
  partition, a Gate 9 or 9.5 read, a promotion streak or safe mode.
  - ADR-0157's ruling 1 already makes practice inert there.
  - A test pins it for this kind: it walks the import graph from the sandbox grader and fails if
    anything reachable writes or reads those.
- **Results never count as evidence** (ruling 5).
  - No gate, certification, review note or decisions entry may cite one as evidence that an
    agent or a manual meets a bar.
  - A sandbox result can inform a manual change, as practice does today.

### 5. Who starts it, and the stops

- **Who.** Ivan Green or Ira Green, each with their own token, or a schedule one of them set.
  The schedule is recorded with its owner, and the owner can stop it.
- **When it refuses to start.**
  - Inside SimForge's sweeps (:17-:24, :47-:54).
  - With free memory under 8 GB. The phi4 rule applies (standing, 4 November).
  - With a live SimForge exam open.
- **Budgets.** A run has a fixed task list, a step budget and a wall-clock budget. It pauses
  inside a sweep and resumes after it.

### 6. The guards

Each guard is a start-up refusal and a test that fails if the guard is removed.

| guard | how |
|---|---|
| Separate deployment and databases | the sandbox Office refuses to start if its DSN, database name, host:port or tenant token equals the live broker's; the sandbox CRE Forge refuses the same against the live Forge; every sandbox row carries `sandbox_run_id` |
| Simulation ventures only | the sandbox setup refuses a venture with no live `venture_simulation` declaration in the live Office (read-only DSN, read once at setup) |
| Outbound credentials empty or it won't start | `SANDBOX_MODE=1` asserts empty Twilio, SendGrid, CoStar, OpenAI and DocuSign settings and exits if any is set |
| Network blocked | the sandbox compose network is `internal: true`: no route out, so a mock that misbehaves still cannot reach anything; a test sends one request out and requires it to fail closed and be logged |
| Sandbox-only machine approver | `sandbox-approver` exists only when `OFFICE_SANDBOX=1`; the live broker refuses the role at creation and at approval, and a live migration's check makes such a row impossible |
| Never touches real grants or data | the sandbox Office has no credential for the live database; its only live read is the simulation check, on the read-only DSN |
| Held-out stays sealed | the generator test above |

## The build, in stages

Sizes are rough: **S** about a day, one PR; **M** two to four days, one or two PRs; **L** about
a week, three or more PRs. Each stage ends with something you can open and check.

| # | stage | repo | size | what you see at the end |
|---|---|---|---|---|
| 1 | Sandbox CRE Forge: the `creforge-sandbox` compose project; `SANDBOX_MODE` start-up refusals; the internal network; the synthetic comps source; the sandbox-only loader | CRE Forge | M | it refuses to start with any outbound credential set, or on the live database or port; with a hand-made world loaded, the three modules answer and comp_analysis says `synthetic`; a test shows a request out failing closed |
| 2 | Synthetic CRE world and tasks: extend the scenario generator (properties, comps, buyers, deals; tasks with expected answers per turn); the held-out isolation test | SimForge | M-L | for a seed, a page listing the world (counts by kind, all marked synthetic) and every task with its facts and expected answers; the same seed gives the same page |
| 3 | Sandbox Office: `OFFICE_SANDBOX` start-up refusals; its own database and migrations; the simulation-only setup; sandbox grants at `propose`; `sandbox-approver` and its refusal on live; filing on the starter's behalf; `sandbox_run_id` | The Office | L | a dry run printing each refusal tried and refused; one task filed, claimed by hand, called, proposed, approved by `sandbox-approver`, all in the sandbox audit log; the live broker refusing the role |
| 4 | Agent shift: a second Village operator instance with a sandbox config and sandbox tokens only | config only (see open point 1) | S | one task claimed and answered by the real operator code path, Turn A and Turn B, against the sandbox |
| 5 | The record and the grade: the `sandbox` run kind and its trace events; per-turn grading with `grade_submitted`; the inertness test | SimForge | M | a first run of a few tasks stored as practice; the certification tables unchanged before and after (counted) |
| 6 | The results page: one HTML page per run, step by step | SimForge | S-M | today's page, extended: per task the facts, Turn A expected and given, the call and the Forge's answer (status and the fields read), the proposal and its approval (actor, time), Turn B expected and given, pass or fail, one line for each miss; totals per module and agent |
| 7 | Start and schedule: the start for Ivan or Ira; a schedule they set; the sweep, memory and open-exam refusals; budgets, pause and resume; stop | SimForge (the run), The Office (the human check) | M | a run started from a block with your token; a scheduled run on its page with its owner; a run that paused in a sweep and finished |

Order: 1 and 2 can go in parallel; 3 needs 1's ports and tokens; 4 needs 3; 5 needs 2; 6 needs 5;
7 last. A first end-to-end run is possible after stage 6 with a hand-started run.

## Open for Ivan

1. **Who runs the agents.** "Agents calling CRE Forge for real" is the Village operator, the
   same code that runs live tasks. That is a fourth repo, though stage 4 is configuration only:
   a second operator instance with a sandbox config. The alternative is SimForge driving Turn A
   and Turn B with its exam runtime. That stays inside three repos but does not exercise the
   operator. The suggestion is the operator.
2. **Which venture first.** Greenstone, whose three read modules are these. Burkham's
   capitalforge modules would need their own sandbox Forge.
3. **The schedule's limits**: how often, and at most how many tasks per run.

## Not decided here

- The write modules (`underwrite_deal`, `assign_contract`), and any module with a signature,
  email, SMS or call path. Each needs its own ruling and its own sandbox fake.
- Any use of a sandbox result as evidence. Ruled out (ruling 5); changing it needs a new ADR.
