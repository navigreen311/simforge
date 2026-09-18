# Four reads, 17 September 2026 — Unit B, ventures, Gate 9.5, and what a real run costs

Read-only. Nothing here was built. Each claim names the file it came from, and the two that were
measured against the live dev database say so.

Companion to [ADR-0058](adr/ADR-0058-the-venture-authors-the-answer-key.md) (the rulings) and
[ADR-0059](adr/ADR-0059-a-pass-carries-its-basis.md) (the build).

---

# 1. Unit B — what a department unit certifies, and what should close one

## Where it stands

`battery.py:605-606` skips every run that is not Unit A, by name: `SKIP_NOT_UNIT_A`. So nothing
scores a department run, and `close_run` reports one only if something else posts an outcome for
it.

**Something worse sits underneath that.** `DepartmentRunOutcome` declares:

    passed: bool = True
    escalation_path_verified: bool = False
    compliance_coupling_verified: bool = False

and `routers/operation.py` reads only `passed` — `elif d_outcome.passed: d_state = CERTIFIED`.
**A department therefore certifies with both verification flags False**, on a payload whose
defaults produce exactly that. The two booleans are recorded, surfaced in the views, and gate
nothing.

## What it is meant to certify

The Office is the side with the definition. `submission_unit` (broker/simforge.py): a submission
naming a module is Unit A; one naming no module is Unit B — *"a department in a Forge, judged
against the domain rubric."* Its basis is `department_basis_hash`, a composite over the
instruction hashes of every module that department's positions operate on that Forge, because a
department has no single operating instruction. And `_department_forge_modules` records why the
grain is (department, forge) rather than (department, venture): *"a position spans Forges … unit B
is required for EVERY Forge a position touches."*

So Unit B is the claim that **this department can operate this Forge's module set in context** —
that work reaches a human where it must, and that the compliance coupling for the venture holds.
Unit A asks whether an agent can drive a module; Unit B asks whether the surrounding department is
a safe place for that module to be driven.

## Three options for what should close one

**A. Gate on the assertions already on the payload.** `certified` requires both booleans True;
either one False holds the unit at `provisional`. One `if`, no new tables, no exam.
*Trade-off:* the booleans remain claims by the caller. This is the exact shape ADR-0059 refused
for the trust tier — a value that travels as though it were measured. It closes the
certifies-with-nothing-verified hole and buys no evidence.

**B. A department battery: probe the escalation path.** The Unit-A analogue. Put a scenario to an
agent acting in that department's context that can only be completed by stopping and handing over,
and grade whether the hand-over reaches the department's declared path.
*Trade-off:* SimForge holds no escalation-path model — who the humans are, per department per
venture, is Office data — so this needs a new fact crossing the boundary before it can be graded.
It is the only option that produces evidence, and it is the most expensive.

**C. Derive Unit B from the Unit A certs over its basis set.** The department is cleared when
every module in `department_basis_hash`'s set holds a current Unit A cert and their escalation
expectations do not conflict. No new exam, and the basis is already recoverable —
`curriculum_submission_module` exists precisely so the composite can be un-hashed.
*Trade-off:* it stops being an independent gate. The Office requires both A and B for every grant
(`provisioning.py`: *"Every grant needs Unit A on its module and Unit B on its department"*), and a
B computed from A adds no second question — it makes the second gate a restatement of the first.

**Recommendation, stated as one:** A now as a stop-gap and B as the real answer, with C rejected
rather than deferred — a derived Unit B would make the Office's two-gate rule cosmetic, which is
worse than an ungraded gate that is honest about being ungraded.

---

# 2. Multiple ventures — every place a venture is missing

## The finding in one line

**The venture is not missing from the wire. It is missing from the schema.** It arrives twice on
every call and is stored nowhere in the operation path.

- `mint_run_ref` (broker/simforge.py) builds
  `office:{venture_id}:{forge_id}:{target}:{hash12}` — the venture is segment 2 of every `run_ref`.
- `X-Office-Venture` arrives on every brokered module call and is written into one log line
  (`routers/office.py:406`, the `origin` dict). Nothing reads it.

## Where a venture is missing

| # | Place | What it is keyed on today | What breaks across ventures |
|---|---|---|---|
| 1 | `ForgeInstructionSet` | no venture column; upsert keys on (forgeId, moduleId, contentHash) | two ventures' answer keys for a same-named module are two rows nothing tells apart |
| 2 | `module_never_do_lists` (never_do.py:293) | scans **every** instruction set, unordered, keeps the first with a list | the battery authors probes from whichever row the DB returns first |
| 3 | `battery_for_run` (battery.py) | picks the instruction set by `createdAt DESC` | a **different** rule from #2 over the same ambiguity — see below |
| 4 | `OperationRun` | no venture column | the venture is in the ref string and unparsed |
| 5 | `OperationCertification`, Unit A | `agentId`/`moduleId`/`forgeId`, no venture | a Unit-A cert cannot say which venture earned it |
| 6 | `gating._latest_unit_a` | (agentId, moduleId) — **not even forgeId** | the newest cert for that pair wins, whatever Forge or venture produced it |
| 7 | `battery_result_for` join | (forgeId, moduleId, agentId) + time bound | its own docstring calls this "a lookup, not an identity"; a venture would not narrow it today |
| 8 | `views.py` side-by-side | Unit A rows carry no venture | the console cannot group or filter Unit A by venture |
| 9 | `routers/office.py` bridge | `X-Office-Venture` logged, never persisted | the one place the fact arrives cleanly and is dropped |

**The only venture-aware query in the operation path** is `gating._latest_unit_b`, which filters on
`OperationCertification.ventureContext` when a caller supplies one — and `ventureContext` is a
free-text Unit-B-only column with no foreign key to the `Venture` registry.

`Venture` itself exists and is populated — six rows in the dev database (`argus`,
`burkham-wickmont`, `caregrid`, `collingswood`, `greenstone`, `medlink-pro`) — and is wired to
Packs, the ontology and spec documents. It is not wired to any operation certification table.

## Can Greenstone's and Burkham's content be kept apart today

**No.** Two ventures submitting a same-named module on one Forge produce two `ForgeInstructionSet`
rows that nothing distinguishes, and rows #2 and #3 above will each pick one — by different rules.

**This is already live on one Forge, with one venture.** Measured against the dev database on
17 September 2026:

| version | authoredBy | createdAt | neverDo |
|---|---|---|---|
| 1.2.0 | ivan | 2026-08-21 | `['overwrite_prior_statement']` |
| 1.0.0 | office | 2026-09-07 | `['never post to the ledger']` |

Both are `capital-forge/statement_ingest`. The unordered scan returns the August row first; the
`createdAt DESC` pick returns the September row. **A battery run on that module today would author
its probes from one prohibition and bind the certification to an instruction set whose prohibition
is a different one.** Not a venture collision — one venture, two rows — but the same mechanism,
firing already.

## The smallest change that would close it

A `ventureId` on `ForgeInstructionSet`, `OperationRun` and `OperationCertification`, sourced from
the header (not parsed out of the ref — a ref format is not a schema), plus the venture in the
selection key of #2, #3 and #6. The two selection rules should also become one rule, whether or not
a venture column lands: that they disagree is a defect on its own.

---

# 3. Gate 9.5 — what a per-venture held-out test and verdict endpoint would take

## What exists

**The Office half is built and blocking.** `_gate_9_5` (provisioning.py:1728) calls a one-method
port, `HeldOutSource.verdict(venture_id) -> str | None`. Its only implementation,
`PartitionAbsent`, returns `None`, and the gate reports
`blocked_by: held_out_partition_not_created` — *"which is the true state of the deployment"*.
Every provisioning run stops there today.

**SimForge's half is a third of the way there.** `held_out.author_for_module` authors probes per
module from a declared never-do list; `held_out_scoring` grades them; the battery runs them
in-process. What does not exist: a per-venture adversarial set, any record of who authored one, and
any way to ask for its verdict.

## The four pieces, and which is the hard one

**(a) A per-venture held-out set — schema + authoring.** A `HeldOutAdversarialSet` keyed by
venture, carrying its scenarios, its author and the approver it must differ from. The existing
per-module authoring is not it: that set is derived from a never-do list The Office sent, and an
adversarial set for ruling 3 is written by a person against the venture as a whole. *Small-to-
medium: one table, one migration, an authoring surface.*

**(b) A verdict endpoint, and the ADR-0050 trap it sits next to.** `GET /operation/held-out/
{venture_id}` returning a verdict and nothing else. It must read a **stored** verdict and must not
be able to trigger a run or return content — ADR-0050's rule is that no credential fetches the
held-out set, and ADR-0057 recorded what happens when a new caller routes around a guard that
walks the import graph from one router. The same care applies: the endpoint must reach a verdict
row and nothing that authors or scores. *Small, and the smallest piece with the largest chance of
being got subtly wrong.*

**(c) The Office adapter.** Replace `PartitionAbsent` with an implementation calling (b). The port
exists, the gate reads it, the verdict vocabulary is already shared. *Trivial — one class and a
config entry. "Nothing else here changes" is the port's own promise.*

**(d) The authorship rule — the hard one.** *"Written by the founder who did not approve that
venture's training content"* needs three facts none of which exist in SimForge: who the founders
are, which one approved the venture's training content, and a check that the set's author is not
that person. The Office has the nearest thing — `office_human` holds identity across ventures, and
`gate_10` records a named sign-off bound to an artifact hash — and SimForge has **no human
registry at all**. So the approver fact originates in one system and the check must run in the
other, which is a port, not a column. *Medium-to-large, and it is a governance design question
before it is code.*

**Sizing:** (c) is one afternoon. (a) and (b) are one package each. (d) is a package of its own
plus a decision from Ivan about where founder identity lives. **Gate 9.5 can be unblocked without
(d)** — a verdict would flow and the gate would pass — but it would be unblocked without the rule
that makes the test worth having, which is a worse state than blocked, because it looks finished.

---

# 4. Setup — what a real battery needs, and what one costs

## The scheduler

- `SCHEDULER_ENABLED=true`. Default is **false** so CI and single-shot runs never spin it up.
- In-process APScheduler (`src/scheduler.py`), cron from `services/cadence/registry.py`.
- `battery_sweep` is registered **hourly at :20** with `triggerable=False` — scheduled, listed,
  inspectable, and **no endpoint can start it** (ADR-0057). There is no way to force a battery from
  a request, by design; to run one now, run the job function or a script.
- `BATTERY_SWEEP_LIMIT = 10` runs per pass, scored serially.
- **Postgres is required in practice.** `battery_sweep_lock` takes a `pg_advisory_lock`; on any
  non-Postgres backend it yields True and takes no lock, which is right for SQLite tests and wrong
  in production.
- Village data must be reachable or the job returns `skipped: village_data_unavailable` rather
  than failing — a deployment fact, not a sweep failure.

## The LLM provider

- `LLM_PROVIDER` defaults to `stub`. **`auto` resolves to Ollama-if-reachable-else-stub and never
  to Anthropic**, so an unattended pass scores with whatever that resolution produced. The job logs
  the examiner in its result for exactly this reason.
- For the named examiner (ADR-0054: `claude-sonnet-5`, measured 11/11 on the A0 probes):
  `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=…`, `ANTHROPIC_AGENT_MODEL=claude-sonnet-5`.
- For local: `LLM_PROVIDER=ollama`, `ollama serve`, `OLLAMA_AGENT_MODEL=llama3.1:8b`. Free, and the
  A0 calibration is why it is not the examiner.

## What one battery costs

Measured, not estimated: probe counts come from `author_for_module` over the live never-do lists,
prompt sizes from `battery_system_context` plus each probe, at ~4 characters per token.

| module | never-do entries | probes | input tokens | cost at $2/$10 per MTok (claude-sonnet-5) |
|---|---|---|---|---|
| `capital-forge/statement_ingest` | 1 | 1 | ~410 | **~$0.001** |
| `capital-forge/reconciliation` | 1 | 1 | ~410 | ~$0.001 |
| `capital-forge/wire_release` | 1 | 1 | ~410 | ~$0.001 |
| `capitalforge/portfolio_health` | 7 | 12 (11 graded) | ~6,100 | **~$0.016** |

Output is 2–3 protocol lines per probe, ~30 tokens, and is inside the figures above.

**A full sweep pass is ten of those: under $0.20 at the largest module's size, and under two cents
at the size the live capital-forge modules actually are.** Hourly, that is a few dollars a day at
the absolute ceiling and pennies in practice, since the sweep only picks up runs with no verdict.
On Ollama the money cost is zero and the cost is local GPU time.

**The expensive thing is not the tokens.** It is that a battery is minutes of live model calls
inside a job the audit chain waits on, which is why it is a separate sweep from the timeout sweep
and why it runs serially.
