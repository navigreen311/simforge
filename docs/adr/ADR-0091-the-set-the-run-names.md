# ADR-0091 — A battery examines the instruction set the run names, never the newest

**Status:** accepted · **Decided by:** Ivan Green, 19 September 2026 · **Built.**
**Follows:** [ADR-0090](ADR-0090-two-conditions-two-reasons.md), which named the skip this rule
now sends four runs to.

---

## The ruling

> **A battery examines a run against the instruction set the run names, never the newest.** Three
> readers disagree with the writer's own key today, and `capital-forge`'s `statement_ingest` is
> live proof: a battery probes the 08-21 never-do list and reports the 09-07 version and hash.

## The writer had a key; nobody enforced it and nobody read it

`operation.py` upserts on `(forgeId, moduleId, contentHash)`. A second hash is a second row **by
design** — that is how a re-authored curriculum is recorded without destroying what earlier runs
executed against.

Three readers keyed on the first two columns:

| | keyed on | order |
|---|---|---|
| `battery.py`, the set to examine against | forge + module | `createdAt DESC`, first |
| `module_never_do_lists`, the list to probe | forge + module | **no `ORDER BY`**, first non-empty |
| `held_out_inventory`, the operator route | forge + module | whatever the above returned |

And nothing made the writer's key real: no unique constraint, no index on `contentHash`.

### The proof was in the database, not in an argument

`capital-forge/statement_ingest`:

```
sha256:adr47-live             v1.0.0  office  2026-09-07  ['never post to the ledger']
sha256:statement_ingest_v1_2_0 v1.2.0  ivan   2026-08-21  ['overwrite_prior_statement']
```

A battery there probed the **08-21** row's rule and reported the **09-07** row's version and hash.
Two rows in one exam, and neither number said which.

`cre-forge/property_lookup` came within hours of the same thing: a probing row written on 19
September, one invented never-do entry, newer than the real set and therefore the one that would
have been examined. It was deleted before a battery ran.

## Built

**1. `battery.py` keys on the run's hash and drops the ordering.** There is nothing left to order —
the hash names one row. `createdAt DESC` answered a different question: *what is the latest
curriculum for this module.* A run is not examined against the latest curriculum.

**2. `module_never_do_list` takes the hash; the bulk form's key is a triple.** Required, not
optional: the only available default is "whichever row turns up", which is the behaviour being
removed. With the hash in the key there is no contention left, so the unordered scan stops
mattering rather than being ordered.

**3. A unique index on `(forgeId, moduleId, contentHash)`** — the writer's own key, enforced. This
is the half that outlives the code: a future writer that keys on two columns now fails loudly
instead of quietly adding a row some reader will prefer.

**4. The operator route says which, instead of picking one.** `held_out_inventory` takes an
optional `?content_hash=`. One set is the ordinary case and stays a plain GET; more than one is a
**422 naming both hashes**. An operator who did not know a module had two sets is better served by
being told than by a number that is true of one of them.

## What it costs: four runs, named

Every open `capital-forge` run carries a hash SimForge holds **no instruction set for at all** —
`sha256:si`, `sha256:office-bridge-first-call`, `sha256:port-move`, `sha256:adr47`. Today they
silently borrow the newest row. Under this rule all four become
**`SKIP_NO_INSTRUCTION_SET`**, which is the honest answer and the reason ADR-0090 built the day
before. The six Greenstone runs are unaffected: each has an exact row.

## What it changed that was not asked for, and why it is right

**`build_gate_result_request`'s VOID clause is no longer reachable from the battery.**
`instruction_set_ref.content_hash` is read off the row the run names, so it now equals
`run_content_hash` by construction and `is_content_hash_void` compares a value with itself.

That is not a lost rule. The old battery-path mismatch was **the reader taking the wrong row**,
reported after the fact — work done against a curriculum the run never saw and then discarded. A
run whose hash SimForge does not hold is now a skip: the same judgement, earlier, and without
thirty-six model calls spent on a result that was going to be voided.

The rule itself is untouched where it belongs. A `GateResultRequest` arrives over the wire, and a
submitter declaring one hash while its run executed another is exactly what the clause catches.
`test_a_content_hash_mismatch_voids_and_is_not_softened` now builds the payload the way such a
submitter would send it, which is also the only way it can now arrive.

## Also in this change

**`app_version` defaults to the started commit.** `openapi.info.version` is what The Office's Gate
8 reads to confirm which build it is talking to, and "1.0.0" was a label the launcher wrote on the
box — it said the same thing whatever code was inside, and said it while this process ran a commit
sixteen behind its own checkout.

**The default was never the problem on its own.** `.env` set `APP_VERSION=1.0.0` explicitly, and an
explicit value beats a default, so the field would have gone on publishing "1.0.0" however it was
declared. That line is deleted in the same change; a default a config file always overrides is not
a default.

Setting `APP_VERSION` still wins and still works: an image stamps it with its own SHA and
`_started_commit` reads the same variable, so the two agree rather than diverge. A release string
is not mistaken for a commit — "1.0.0" is not hex, and `_started_commit` falls through to the
working tree.

**OTel `service.version` becomes a 40-character commit SHA** (`telemetry/tracing.py`). That is the
one consequence outside this repository, and it is acceptable: a resource attribute exists to say
which build emitted a span, and a commit answers that where "1.0.0" — unchanged since the service
was created — never did. It is a free-form string in the OTel semantic conventions, so nothing
rejects it. What it costs is any dashboard that groups or filters on a *fixed* `service.version`
value; there are none in this repository, and a deployment that wants semver back sets
`APP_VERSION` to it, which is the escape hatch that was always there.

## Tested

`test_the_set_the_run_names.py`, seven tests, each written to **fail on the old rule** — every
fixture gives the module a second, newer set, which is the state under which the two rules diverge:

- the battery examines the set the run names, with a newer one present
- a run naming a hash no set carries skips by name
- two sets for one module are two entries in the bulk form, not one
- `instruction_set_hashes` reports both, newest first
- the inventory route refuses with 422 and names both hashes
- it answers when told which set
- and it is unchanged for a module with one set

Suite: **1,109 pass, 2 skip.** `SCHEDULER_ENABLED` stays off.
