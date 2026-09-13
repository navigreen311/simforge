# ADR-0057 — The cadence may schedule what no endpoint may trigger

**Status:** accepted · **Decided by:** Ivan, 12 September 2026 · **Built by:** the coordinator
**Supersedes nothing. Extends:** ADR-0050 (no credential fetches the held-out set).

---

## The question

`sweep_unscored_runs` was built, correct, and dead. It selects the right rows — open Unit-A runs
with no verdict, oldest first — and nothing invoked it. `src/workers/__init__.py` says so in its
own docstring: *"Imported by no router — see ADR-0050 and `battery_sweep`."* The registration was
the only missing piece.

The cadence registry is where a scheduled job goes. **But registering it there would also have
handed the battery an HTTP verb**, because `POST /api/scheduler/run/{job_name}` runs anything in
`JOBS_BY_NAME`.

## Why that is not a small thing

ADR-0050's rule is that no credential fetches the held-out set. Its guard test states the
consequence:

> *"So there is NO endpoint that triggers a battery: it is reached from a process-side caller, and
> this is what says so."*

That test walks the import graph from `src.routers.operation`. **It cannot see
`src.routers.cadence`.** And `jobs.py` imports every dependency inside the function body by
convention, so no import-graph walk from anywhere would have found the edge.

Registering the sweep would therefore have **passed ADR-0050's guard while defeating ADR-0050's
rule** — which is the precise shape that ADR names as the worse outcome:

> A fetch endpoint would not contradict that rule; it would route around it. **The submitter would
> not author the probes — it would read them, which is worse, because it looks compliant.**

**The role dependency is not a fallback.** ADR-0050 already read `Principal.has_role` out of the
code: `return role in self.roles or "admin" in self.roles`. Any check answers True once `admin` is
present, so `require_role("admin")` on the trigger endpoint gates nothing.

## The decision

**`CadenceJob.triggerable`.** A job may be scheduled, listed and inspected without being startable
by request. `battery_sweep` is registered with `triggerable=False`, and `run_job` refuses it.

**403, not 404.** The job exists, is scheduled and appears in `/status`. Answering as though it
were unknown would hide a running job from an operator in order to enforce a rule about who may
*start* it — two different questions, and only one of them is ADR-0050's.

**Hourly at :20, and the interval is not a preference.** `DEFAULT_RUN_WINDOW_MINUTES = 180`, and
`unscored_runs` deliberately will not re-score a run already stamped TIMEOUT. A daily sweep would
arrive after almost every run had left the filter: **registered, running, and permanently empty.**
Hourly leaves a run at worst 60 of its 180 minutes waiting and at least 120 for a battery that
"can take minutes".

## What giving it a caller immediately found

Both of these had shipped, been reviewed, and passed their tests. Neither had ever run.

**1. The advisory lock was malformed for this service's driver.** `battery_sweep_lock` used
`exec_driver_sql("... hashtext(%s)", (LOCK_KEY,))`. `%s` is psycopg's paramstyle; `config.py`
rewrites every URL to `postgresql+asyncpg://`, and asyncpg's is `$1`. The first time the statement
reached a Postgres connection it raised `syntax error at or near "%"`.

**Its two tests both passed throughout.** One asserts the **SQLite** branch — the branch whose
entire behaviour is to take no lock and return. The other asserts the module's **source text**
contains `dialect.name != "postgresql"`. Between them they covered the shape of the code and the
branch that does nothing, and neither ever sent the statement anywhere.

CI has no Postgres service, so a live test would be permanently skipped — the same hiding mechanism
wearing a different hat. The guard added instead **compiles the statement against the asyncpg
dialect** and asserts it renders `$1` and not `%s`: no database, and it fails on exactly the defect
that shipped.

**2. The lock cannot ride the session the sweep rolls back.** `sweep_unscored_runs` calls
`session.rollback()` for every run whose battery raises — that is what lets one bad run not end the
pass. A rollback hands the connection back, so holding the lock on the swept session means the
first failed run closes the connection the unlock needs, and the pass dies in
`ResourceClosedError` having already computed its outcome. **The lock gets its own session.**
Observed, not theorised.

### The thread connecting them

`battery_sweep.py` carries four headed sections of careful prose about ordering, staleness windows,
why the lock is pinned to one connection, and why the dialect is checked rather than wrapped in a
bare `except`. **Every one of those paragraphs is correct.** The module was still broken two ways,
because prose about a statement is not an execution of it — and the tests that existed asserted the
prose and the inert branch.

**A caller is a test that cannot be satisfied by describing itself.** Registering this sweep found
in one run what nine days of review had not.

## A note on the examiner, which the job now reports

`LLM_PROVIDER` defaults to `stub`, and `auto` resolves to ollama-if-reachable-else-stub — **never
anthropic**. A scheduled pass scores with whatever that resolution produced, unattended. This is
not silent: `battery_for_run` already records `agentModel=provider_label(runtime.provider)` on the
certification. The job surfaces it in its result as well, so the operator reading the job log sees
which examiner sat the exam without opening a cert.
