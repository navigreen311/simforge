# ADR-0166 — An autonomous sandbox run

**Status:** accepted · **Decided by:** Ivan Green, 2026-11-08 and 2026-11-09 · **Stages 2, 5,
6 and 7 built in SimForge (stage 1 in CRE Forge; 3 and 4 open as The Office #521 and
village-os #25).**
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

## The rulings on the open points (Ivan Green, 2026-11-09)

> 1. The real Village operator runs the agents (a second instance with a sandbox config).
> 2. Greenstone goes first.
> 3. Schedule: at most one scheduled run per business day, max 60 tasks per run, never in
>    :17-:24 or :47-:54, memory gate applies. Hand-started runs any time outside the sweeps.

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
7. **The record.** Each of steps 1 to 6 is a step on the run, carrying the task id, the
   sandbox ids and the timestamps (as built: a `SandboxStep`, not a `TraceEvent`; see stage 5).

**Sandbox grants** are created by the sandbox setup from the venture's Pack:

- the three read modules only;
- the agents the Pack names;
- tier `propose`, never `auto_execute`.

They are not issued by provisioning: no gate runs in the sandbox, and no live grant is read,
copied or changed.

### 4. The record and the grade

- **A sandbox run is a SimForge practice record** (ruling 1).
  - It is a record of its own kind, so it is never counted as a practice battery and can never
    be mistaken for an exam. As built it is its own table, `SandboxRun`, not a `Run` with a
    kind (stage 5 says why).
  - It holds its steps as `SandboxStep`s.
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

## The open points, ruled (9 November)

1. **Who runs the agents: the Village operator.** A second operator instance with a sandbox
   config holding only sandbox agent tokens (stage 4, configuration only). SimForge does not
   drive Turn A or Turn B with its exam runtime.
2. **Which venture first: Greenstone.** Its three read modules are the ones the world is built
   for. Burkham's capitalforge modules wait for their own sandbox Forge.
3. **The schedule (stage 7):**
   - at most one scheduled run per business day;
   - at most 60 tasks per run;
   - never inside :17-:24 or :47-:54;
   - the memory gate applies (free memory under 8 GB refuses, as section 5);
   - a hand-started run, by Ivan or Ira, may start at any time outside the sweeps.

## Stage 2, as built

`apps/api/src/services/forges/deal_desk_world.py`, next to `deal_desk.py`, whose engine gains
`seed_world(tenant_id, seed)`.

- **The world, for one seed.** 28-38 properties in four of eight invented markets, sales comps
  for about half of them, 18-24 buyers with status, do-not-contact and a price range, and 7-9
  deals. Every row carries `synthetic: true`, the seed and `GENERATOR_VERSION` (1.0.0). Buyer
  emails end `@synthetic.invalid` (1.0.0; `@sandbox.invalid` from 1.1.0, stage 5).
- **Same seed, same world.** Everything comes from `random.Random(seed)`. Ids are `uuid5` over
  the version, the seed and the row's place (1.0.0; from 1.1.0 they are CRE Forge's loader ids,
  stage 5). No clock, environment, file or database is read.
  `world_digest` and `tasks_digest` are sha256 over canonical JSON.
- **20 tasks per seed**, in `happy_path`, `partial_failure` and `malformed_input` only:
  - **property_lookup, 6:** two city counts, the silent `page_size` cap, an address on no row,
    and the two missing-field counts.
  - **comp_analysis, 9:** a count, a count under `max_comps: 2`, a property whose comps are all
    outside the default search, a widening with a reason, four policy refusals (over the cap,
    no reason, age 0, age over the cap), and an unknown property.
  - **buyer_match, 5:** a count, a count under `limit: 2`, a deal whose every in-band buyer is
    do-not-contact, `limit: 0`, and an unknown deal.
- **Each task carries:**
  - the facts a person files and the request fields;
  - **Turn A**, the ACT before any call. It is PROCEED, or PROCEED or DECLINE where the request
    breaks a published bound, since the pre-call ACT is not certified (The Office's entry 254);
  - **the Forge's answer, predicted from the world** with CRE Forge's own rules as of
    medlink-wholesale `9f532fe`: the substring search and the 100-row cap, the B117 comp policy,
    the buyer price band and `suppressed`;
  - **Turn B**, the ACT and RECORD on that answer. It is graded only when Turn A was PROCEED.

  Both turns are written in `SubmittedKey`'s fields, with subjects and claims in the approved
  keys' vocabulary, and `grade_submitted` grades them unchanged.
- **Stage 1's contract for comps.** A comp names its subject, `distance_mi` and
  `sale_age_days`. The sandbox source returns a subject's comps within the searched radius,
  nearest first, and the loader dates each sale that many days before the day it loads.
  Distances sit at least 20% of a band from every bound, and ages at least 35 days from 365 and
  730. The days between loading and running therefore cannot move a count.
- **The page.** `python -m scripts.sandbox_world_page --seed N --out DIR` writes
  `world-seed-N.html`. The page shows:
  - the generator version and both digests;
  - the world's counts by kind, and every row;
  - every task with its facts, request, Turn A expected, the predicted answer, Turn B expected
    and notes.

  It has no timestamp, so the same seed gives the same bytes.
- **Held-out stays sealed.** `tests/unit/forges/test_the_sandbox_world_is_sealed_off.py`
  requires that:
  - the generator and the page script reach no SimForge module but the generator;
  - the generator imports only eight standard-library modules;
  - it calls nothing that opens a file, reads the environment or imports by name;
  - it names nothing held out (no `held_out`, `never_do`, `partition`, `look_alike`).

  The test also shows that a held-out import would be caught.
  `test_deal_desk_world.py` checks, for 50 seeds, that no task is `never_do_violation`,
  `silent_failure` or `permitted_request`, and that a seed has at most 60 tasks.
- **What it does not do.** It loads nothing into a Forge, files nothing and grades no agent.
  That is stages 1, 3, 5 and 7. If CRE Forge changes one of the rules above, a predicted
  answer can go stale without this module changing; stage 5 will show that as a miss on the
  Forge's side, not the agent's.

## The world file: SimForge's export, CRE Forge's loader (agreed 9 November)

SimForge writes the world in the format CRE Forge's sandbox loader already reads
(`backend/app/sandbox/loader.py`, medlink-wholesale `90fadc6`; `worlds/hand-made-1.json` is the
other example). Nothing in the loader changed. The agreement:

- **One file per seed**, `simforge-<generator version>-seed-<n>.json`. Its `world` is that
  name, and its `version` is the generator version.
- **Ids are the loader's.** The loader gives a row the id `uuid5(NAMESPACE, "<world>/<key>")`,
  with its fixed namespace `5a4d0c66-0166-4e2b-9b1a-5a4db0c0ffee`. A comp's key is
  `<property key>/comp-<i>`, where `i` is its place under its subject. The generator computes
  the same ids (`row_id`), so a task names the ids the sandbox Forge holds once the file is
  loaded. A new generator version is a new world name, and so every id moves with it.
- **Shape**, as the loader reads it:
  - `properties[]`: `key`, `address`, `city`, `state`, `zip_code`, `county`, `property_type`,
    `status`, `square_feet`, `asking_price`, and `comps[]` nested under each.
  - `comps[]`: `address`, `days_ago`, `sale_price`, `square_feet`, `distance_miles`,
    `similarity_score`. The loader dates each sale `days_ago` days before the day it loads.
  - `deals[]`: `key`, `property` (a property's key), `deal_name`, `status`, `stage`,
    `asking_price`, `contract_price`.
  - `buyers[]`: `key`, `name`, `buyer_type`, `status`, `do_not_contact`, `min_price`,
    `max_price`, `preferred_cities`, `preferred_states`, `preferred_property_types`,
    `financing_type`.
  - Money is a decimal string or null. Enum values are CRE Forge's own.
  - The loader makes some fields itself, so the file leaves them out: buyer email
    (`<key>@sandbox.invalid`) and phone, a comp's city, state and zip (its subject's),
    `source = 'synthetic'` and deal notes.
  - Extra keys are ignored by the loader: `seed`, `generator_version`, `world_digest`,
    `tasks_digest`, `about`.
- **One world per sandbox database.** The tasks count every row the Forge holds. A database
  that also holds `hand-made-1`, or another seed, gives other answers. The loader is additive
  and does not check this. Stage 7 must load each run's world into an empty `creforge_sandbox`
  database.
- **Where the loader reads it.** The loader reads by name from `backend/app/sandbox/worlds/` in
  the checkout the sandbox mounts read-only. So today the file is copied there on the host, and
  then `docker exec creforge-sandbox-backend python -m app.sandbox.loader <name>` is run. A
  path argument would be a small CRE Forge change. It has not been made.

## Stage 5, as built

- **The record: its own tables, not `Run`.** `SandboxRun` and `SandboxStep` (migration
  `20261109000000_a_sandbox_run_of_its_own`; `src/models/sandbox_run.py`). This is a change
  from section 4, which said a `Run` with a kind:
  - `Run` needs a scenario, a pack and one agent. A sandbox run has none of those.
  - `Run.executionMode = "sandbox"` already means a non-integrated practice run.
  - The practice hooks, the runs list and the budget all read `Run`.

  A table nothing else reads cannot be mistaken for any of them. It also does not touch
  `is_practice_run`.
- **A run** is opened by Ivan Green or Ira Green, optionally under a schedule one of them owns.
  It is for `greenstone` and `cre-forge` only, has one seed, and a fixed task list of at most 60
  tasks. It records the generator version, the loader world name and both digests.
- **Each step**, in order per task: `filed`, `claimed`, `turn_a`, `proposed`, `approved`,
  `forge_answer`, `turn_b`. Each carries its time, actor, agent, the sandbox's own ids and its
  payload. Out of order is refused, and so are:
  - a step after the task ended;
  - filing by anyone but the starter or the schedule owner;
  - an approval by anyone but `sandbox-approver`;
  - another agent than the claimant;
  - any step once the run is closed.

  Each refusal is a code, and nothing is written.
- **The grade.**
  - **Turn A** is graded by `grade_submitted` against the task's Turn A key. Anything but
    PROCEED ends the task.
  - **`forge_answer`** keeps the predicted fields read off the Forge's response
    (`forge_fields`; null counts are read off `results`) and records `forgeMatches`.
  - **Turn B** is graded against the Turn B key, but only if the Forge answered as predicted.
    Otherwise it is `NOT_GRADED`, with `forge_answer_differs_from_prediction`: the key was
    written for an answer the agent never saw, so the miss is the Forge's, not the agent's.
  - No turn is graded once the generator in force would give other tasks (`generator_moved`).
  - Answers arrive structured, as The Office records them: an act, a record and caveats, or
    `{"unreadable": <protocol rule>}`. No prose is read.
- **Close** writes the totals once: per module and per agent, tasks, tasks ended, Turn A and
  Turn B verdicts, and Forge mismatches.
- **The generator, 1.1.0.**
  - Ids are the loader's, and buyer emails are the loader's.
  - Comps carry `similarity_score`, buyers `financing_type`, and deals `deal_name` and `stage`.
    These are derived, not drawn, so every 1.0.0 draw is unchanged.
  - `comps_found` counts as the sandbox source does: the `2 * max_comps` nearest inside the
    radius, then the age window. No 1.0.0 task changed count because of this.
  - The two 404 predictions now carry the Forge's own body,
    `"<Kind> with id '<id>' not found"`.
  - `export_world` and `export_json` write the world file;
    `python -m scripts.sandbox_world_page --seed N --out DIR --export` writes it beside the
    page.
- **Checked against the real sandbox Forge (9 November, read only).** This used CRE Forge's
  merged code (`90fadc6`) and its sandbox image, on a throwaway internal network, with one
  fresh Postgres database per seed:
  - its start-up guards passed;
  - its own loader loaded each file;
  - every task's request was put to `/forge/<module>`;
  - the answer was read with `forge_differs`.

  **200 of 200 tasks over seeds 0-9 answered as predicted.** The two 404 shapes above were
  found this way and fixed. The live CRE Forge and the running sandbox stack were not touched,
  and the throwaway stack was removed. This check is not in CI: CI has neither CRE Forge nor
  Docker.
- **Inert, counted.** `tests/unit/forges/test_a_sandbox_run_reaches_no_exam_or_certification.py`
  records a five-task run (passes, a wrong count, a Turn A DECLINE, a Forge that differed). The
  database it runs on already holds an exam, a certification with a tier and a partition.
  - Every table's count is the same before and after, except the two sandbox tables.
  - Every row of every other table reads back unchanged.
  - No statement during the run names any other table, read or write.
  - The import walk from the record reaches only the generator, its own model, and the grader
    with that grader's own imports. That includes the approved-key model it types from; the
    record calls only `grade_submitted`.
  - Negative controls show the count and the walk would each catch an exam write or import.
- **Not done here.**
  - No run against live agents: there is no sandbox Office or agent shift yet (stages 3 and 4).
  - No route: the stage 7 driver calls the record directly.
  - No page per run (stage 6; built 10 November, below).
  - The migration is not applied to the dev database. Applying it (`prisma migrate deploy`,
    or its SQL) is a deploy step, and it was not taken here.

## Stage 6, as built (10 November)

- **One HTML page per sandbox run**, from `SandboxRun` and its `SandboxStep`s and nothing else
  (`src/services/sandbox/page.py`). Laid out like the 8 November practice page, but step by step:
  - **Totals** per module and per agent: tasks, tasks finished, tasks passing, Turn A pass/fail,
    Turn B pass/fail/not graded, Forge mismatches. The turn counts are the totals the run wrote
    when it closed, or counted the same way, and labelled as such, while it is open. Tasks
    passing and finished are counted from the steps.
  - **Every task** on one line: Turn A, Turn B, its result, and a one-line why for each miss.
  - **Then each task step by step:** the facts filed, the claim, Turn A expected and given, the
    call proposed (expected and as proposed), the approval (actor and time), the Forge's answer
    (predicted and read), Turn B expected and given. Each step has its time, actor and the
    sandbox's ids. Each graded step has its verdict and why.
- **A task's result:** FAIL if a turn failed; else UNFINISHED if it never ended (the page shows
  the step it was waiting at); else NOT GRADED if Turn B went ungraded because the Forge
  differed; else PASS. A Turn A other than PROCEED that the key allows is a PASS with no call.
- **The why** is built from the grader's reason codes and the values compared, for example
  "Turn B: recorded 9 for total; the key expects 8", or "the Forge's status was 503, predicted
  200". A protocol violation names the rule. A code the page does not know is shown as the code:
  the page never invents a cause.
- **Expected answers** are the generator's, regenerated from the seed. If the generator in force
  would give other tasks, the page says so and shows the recorded verdicts without expected
  answers.
- **Reads only.** `load_run` selects one run and its steps. Rendering reads no database, and the
  page carries no time of its own, so the same rows give the same bytes. The inertness test now
  also walks the page's and the demo's imports, and checks that loading and rendering a page
  issues only SELECTs, naming only the two sandbox tables, with every count and row unchanged.
- **The script.** From `apps/api`:
  - `python -m scripts.sandbox_run_page --run <runRef> --out DIR` reads a run from the database
    and writes `sandbox-run-<runRef>.html`. There are no real runs yet, and the migration is not
    applied to the dev database.
  - `python -m scripts.sandbox_run_page --demo --out DIR` writes `sandbox-run-demo.html`.
- **The demo: a recorded fake run** (`src/services/sandbox/demo.py`). Thirteen seed 0 tasks,
  recorded through the real `open_run`, `record_step` and `close_run` and graded by the real
  grader. The database is in-memory SQLite and holds only the two sandbox tables. No agent
  answered and no Forge was called: the answers are scripted, the Forge's answer is the
  prediction except where a mismatch is staged, and the agents are `fake-agent-1` to `-3`. The
  page says so in red at the top. It stages, across the three modules:
  - four plain passes (two property_lookup, one comp_analysis, one buyer_match);
  - a wrong count, a missing caveat, a record under the wrong subject;
  - a Turn A DECLINE the key does not allow, and one it does;
  - a Turn B claim not on the list;
  - an answer that broke the protocol;
  - a Forge answer other than predicted, so Turn B is not graded;
  - a task left waiting for its approval.

  Result: 5 of 13 pass, 6 fail, 1 not graded, 1 unfinished.
- **Not done here.** No route or web page in the dashboard: the page is a file, like stage 2's.
  No run with real agents (stages 3 and 4).

## Stage 7, as built (10 November)

`python -m scripts.sandbox_run` (`src/services/sandbox/runner.py`, `rules.py`,
`office_sync.py`); how to use it is in [docs/sandbox-runner.md](../sandbox-runner.md).

- **One run, start to stop.**
  1. The start rules.
  2. A seed: the next after the last one run, unless named. Its tasks are taken one module at
     a time in turn.
  3. The seed's world loaded into the shared sandbox CRE Forge (8012) by its own loader with
     `--replace`.
  4. A fresh sandbox Office: `office_sandbox` dropped and made again, migrated, set up for
     Greenstone, served on 9212.
  5. The sandbox operator set up from the Office's fresh tokens.
  6. The starter, with their own sandbox token, starts the Office's run and files up to N
     tasks.
  7. The `SandboxRun` opens on the tasks filed. The operator then ticks one step at a time,
     each proposal is approved by `sandbox-approver` at the starter's request, and every step
     the Office wrote is recorded as a `SandboxStep`, with the Office's times.
  8. The Office's run is finished, the `SandboxRun` closed and the page written.
  9. Everything the run started is stopped.
- **The rules**, each a refusal with every reason reported (`rules.check_start`):
  - Ivan or Ira only;
  - 1 to 60 tasks;
  - never inside :17-:24 or :47-:54 (a hand start is refused; a scheduled one waits);
  - no SimForge exam open;
  - 8 GB free, after the phi4 rule (phi4 unloaded first if loaded, no exam open and outside
    the sweeps);
  - one run at a time (a lock);
  - 9212 free;
  - the checkouts, the Forge's env, a loader with `--replace`, and SimForge's sandbox tables
    all present.

  A scheduled run also refuses on a weekend, after a scheduled run already started that day,
  or with its schedule stopped.
- **Pause, budgets, stop.**
  - A run pauses inside a sweep or while a SimForge exam is open (no tick, no approval) and
    resumes after.
  - It stops at its tick budget, at its wall-clock budget, after 8 ticks in a row that record
    nothing, or on `stop`.
  - Whichever ends it, the run is closed and its page written, with unfinished tasks shown as
    such.
- **The schedule** is `schedule.json` in the runner's own directory: an owner, a time, a task
  count. It is not a table: every run it starts records its owner on
  `SandboxRun.scheduleOwner`, which is what the page shows. Only the owner stops or replaces it.
  `--register` makes the Windows scheduled task (business days at that time).
- **What a task is filed with.** The task's request, plus the generator's facts as
  `instruction`. A read whose facts carry a person's words keeps Turn A (The Office's B113),
  and the record grades Turn A. Without it the Office skips Turn A on a read (entry 256), and
  no step after `claimed` could be recorded.
- **What is read from The Office**, SELECT only, from its own database
  (`office_sync.OFFICE_TASK_SQL`):
  - acts and records as the Office parsed them;
  - caveats counted by the Office (`caveat_lines` on its log);
  - an answer that broke the grammar twice, as the rule its `agent_answer_malformed` entry
    names;
  - the Forge's status and body;
  - the approver by `office_human.origin`.

  A step not yet written stops the list for that task; nothing after a gap is guessed. A step
  the record refuses (for example an approval by anyone but `sandbox-approver`) stops that
  task's recording and is named in `summary.json`.
- **A filing the Office refuses** (B117: a radius or window above the default with no
  `widening_reason`) is skipped and the next task is tried. Ruled by Ivan Green, 10 November:
  the generator keeps making such tasks. The run keeps each refusal
  (`totals["refused_at_filing"]`: the task, the Office's status and reason), and the page shows
  it as "refused at filing by The Office", apart from the run's tasks and counted against no
  agent. The `SandboxRun`'s tasks are the tasks filed only.
- **Also ruled 10 November:** Turn A stays on every task (real filings carry a person's words);
  dropping the previous sandbox Office database each run and unloading phi4 after a run are
  approved.
- **Writes only its own two tables.** `test_sandbox_runner` counts every INSERT, UPDATE and
  DELETE during a run: `SandboxRun` and `SandboxStep`, nothing else. The runner reads
  `OperationRun` only to refuse or pause while an exam is open.
- **Tested.**
  - In CI, the loop runs against a fake Office: every step recorded and graded, a filing
    refused, a Forge that differed, a sweep pause and resume, an exam pause, each budget, a
    stop, an operator that records nothing, and writes counted.
  - On throwaway stacks (10 November), the real runner ran: a throwaway CRE Forge (8013), a
    throwaway Office Postgres (55443) with a stand-in for the simulation declaration, the real
    sandbox Office broker (#521 at 7f137c2) on 9212, the real sandbox operator (#25 at aead1e5)
    on phi4, and a throwaway SimForge database. All of these runs are practice and none is
    evidence.
    Seven runs, seeds 0 to 6:
    - **Seed 0** found that The Office refused every answer (`ModelMismatch`): the digest was
      not in the live form `sha256:<hex>`. #521 fixed its side at 7f137c2, and the runner now
      passes the digest in that form. That run ended on its tick budget, and is why a run now
      stops after 8 ticks that record nothing.
    - **Seeds 1, 3, 5:** 4, 4 and 3 tasks, every one finished. Seed 3 started at 13:16:58,
      paused at 13:17:19 inside the sweep, resumed at 13:25:19 and finished.
    - **Seed 2:** Ira Green, all 20 tasks. The Office refused 2 at filing (s2-012 and s2-014,
      B117), so 18 were filed and all 18 finished. Turn A: 9 PASS, 9 FAIL; 7 of the failures
      are comp_analysis REFUSE or ESCALATE before the call. Turn B: 6 PASS, 3 FAIL. 6 of 18
      tasks pass.
    - **Seed 4:** a scheduled run on Ira's schedule, recorded with `scheduleOwner` and shown
      on its page. A second `scheduled` the same day was refused
      (`scheduled_run_already_today`); Ivan could not stop Ira's schedule; Ira could.
    - **Seed 6:** stopped by `stop` after its third tick. It closed with 5 of 18 tasks
      finished, and the page shows the rest as unfinished.
    - **The Forge:** 22 calls in all, and every answer matched the generator's prediction, with
      `instruction` in the facts.
    - **Time zone:** the record's times round-trip only on a server whose `TimeZone` is the
      machine's own, as SimForge's database is (America/Los_Angeles). On a UTC server the
      stored times moved 8 hours. The throwaway database was set to SimForge's zone, and a page
      written again from it was byte-identical to the run's own.
- **Migration 20261109000000 is not applied** to SimForge's database, and the runner refuses
  until it is. Founder block 135 applies it (drafted, not run). It was tested on a throwaway
  database holding SimForge's schema as it stood before #269.

## The first real run, audited (10 November)

Run `sandbox-01M73YAV88WWRG7F7CFFCVY2NP`: Ivan Green, seed 0, generator 1.1.0, 18 tasks filed,
2 refused at filing, 6 passing. Each of the 12 misses was read against the live CRE Forge
manuals 1.11.9 (property_lookup `fbf770550a29`, comp_analysis `bdea91488bc6`, buyer_match
`264e47beeedc`, recomputed from The Office's `author_cre_forge_instructions.py` with its own
`instruction_hash`) and The Office's decisions up to entry 338.

- **Key wrong, fixed: generator 1.1.1.** s0-005 and s0-006 asked for "the Corvale properties
  with their asking price" (and square feet), and the key recorded the count missing. The manual
  makes that count the record only when it is the question: "ONE RECORD LINE: asked how many lack
  a price, the record is that count". The facts now ask how many have none recorded; nothing
  else moves. The world's rows are unchanged, but its name, and so its ids, carry the version,
  so CRE Forge's loader has to accept 1.1.1 (`SUPPORTED_VERSIONS`) before a run on it loads.
  Run `sandbox-01M73YAV88WWRG7F7CFFCVY2NP` was graded under 1.1.0; its page, written again,
  says the generator moved.
- **Agent wrong:** s0-003, s0-007, s0-008, s0-009, s0-010 (its record), s0-013, s0-015, s0-019,
  s0-020. They go to The Office as manual changes.
- **Needs a ruling:** s0-011, and with it s0-010's Turn A: whether "too few recent sales inside
  the default radius for this property type" is a constraint of the property.
- **The grade flags a CAVEAT that states a count the Forge's answer contradicts**
  (`caveat_contradicts_forge`), and changes no verdict (`docs/sandbox-runner.md`, "What the
  grade flags"). s0-001 and s0-002 said "returned 100 properties" of a `total: 8`.

## Not decided here

- The write modules (`underwrite_deal`, `assign_contract`), and any module with a signature,
  email, SMS or call path. Each needs its own ruling and its own sandbox fake.
- Any use of a sandbox result as evidence. Ruled out (ruling 5); changing it needs a new ADR.
