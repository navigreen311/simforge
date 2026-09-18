# ADR-0065 — Identity is read from the live Village database, and the prompt uses the title

**Status:** accepted · **Decided by:** Ivan Green, 17 September 2026 · **Built by:** the coordinator
**Implements:** ADR-0063 ruling 2. **Extends:** ADR-0061 (a lookup that finds nothing refuses).

---

## The rulings

**1. Identity is read from the live Village database, not a snapshot. A snapshot that goes stale
silently is the defect.**

**2. The prompt uses the agent's title, falling back to role. "A individual_contributor" is not who
Victor Serath is.**

---

## The defect, measured

    village.db `agents`        186 rows   (written seconds before the measurement)
    VillageData/agents/        114 dirs   (unchanged since 2026-08-28 11:19)
    in both                      1        (`gardner`)

Two different populations. The tree was generated for an earlier cast at 11:19; the agents that
exist now were created at 21:17 the same evening and nothing regenerated it. `VillageReader` spent
three weeks describing agents that were not running, and **nothing said so** — every missing-agent
read was swallowed by `AgentRuntime._safe`, and the prompt papered over it with the id as a name.

The alternative — regenerate the tree on a cadence — was rejected in the report and the reason is
the ruling's own words: **a regenerated tree is still a snapshot.** The only open question would be
how long until the next one goes stale.

## The decision

`VillageReader` gains `village_db_path`. When it is set, **identity comes from the database** and
the tree is used only for the frameworks the database does not hold.

`from_settings()` reads `VILLAGE_DB_PATH`, which was already a declared setting that nothing used.
So a real deployment is database-backed unless somebody empties it deliberately.

**A configured database that is missing is loud on every lookup.** It does not fall back to the
tree beside it. That fall-back is precisely how a deployment would go on answering confidently from
a stale snapshot, which is the thing being ruled out — `test_a_configured_database_that_is_missing_
is_loud_not_a_fallback` holds it.

**The database wins even when the tree still has the agent.** Especially then: a stale tree that
still holds an entry is the case that produced a *wrong* answer rather than no answer.

`identity_source` (`village_db` | `snapshot`) is on the reader and on `GET /api/health/status`,
beside `village_population`. The failure this ADR closes hid for three weeks because nothing
reported which source was answering.

### Read-only, against a live writer

`file:<path>?mode=ro`. The Village is running and writing; `village.db-wal` sits beside the file.

**Never `immutable=1`** — that flag promises the file cannot change and lets SQLite skip the WAL,
which against an active writer means reading a stale page and calling it current. Not doing that is
the entire point.

### Ruling 2, in one line

`role` in this database is an org role **key** — `individual_contributor` — and `title` is the job:
`Trend Analyst 2`. The tree's `role` was a job title, so a straight column swap would have put
*"You are Victor Serath, a individual_contributor"* into every prompt.

`title` first, `role` as fallback. The org role is kept beside it as `org_role` rather than
discarded: it is a real fact, and a later reader should not have to guess which of the two `role`
meant.

## What it does, live

Against the real `village.db` (186 agents):

    victor_serath      ok=True   'Victor Serath'    / 'Trend Analyst 2'
    ronan_valek        ok=True   'Ronan Valek'      / 'Project Manager 2'
    seraphine_valek    ok=True   'Seraphine Valek'  / 'Client Liaison 4'

and against the snapshot the battery has been reading:

    victor_serath      ok=False  the_agent_is_not_in_the_village_tree
    ronan_valek        ok=False  the_agent_is_not_in_the_village_tree
    seraphine_valek    ok=False  the_agent_is_not_in_the_village_tree

**All three Greenstone agents are now identifiable.** ADR-0061's refusal stops firing for them,
which was the last thing standing between a run and a battery.

## What the prompt loses — and it is more than backstory and traits

The identity layer, rendered:

```
--- DB-backed, victor_serath ---
You are Victor Serath, a Trend Analyst 2.

Respond in character, naturally and professionally.
```

```
--- snapshot-backed, taylor_zhang (the fixture) ---
You are Taylor Zhang, a Senior Engineer.
Backstory: Joined Greenstone Engineering after years in fintech infra.
Personality traits: meticulous, calm-under-pressure, mentoring
Core character (BREATH): beliefs, rituals, ethics, attachments, traditions, habits.
Current pressure (FOT): tier=stable.
Emotional state (SOUL): focused, valence 0.62.
Recent episode: Resolved a production incident calmly.

Respond in character, naturally and professionally.
```

**Two lines against eight.** The loss is not only the two fields the question named — for these
agents the database has an empty `backstory` and `[]` traits, *and* BREATH, FOT, SOUL and the
recent episode all still come from the tree, which has no directory for them at all. So a DB-backed
prompt for a real agent is name, title, and the closing instruction.

### Does it matter?

**Not for what the exam grades, and yes for what the certification claims.**

The battery appends `battery_system_context` — the module, its numbered prohibitions, the answer
protocol — and grades refusal and concealment against *those*. None of the nine Village layers is
part of the grading key, and the measured run that took phi4 from 3/16 to 16/16 was made against a
prompt this thin.

But the certification says **Victor Serath** passed. With a two-line identity layer, Victor Serath
and Ronan Valek receive prompts differing in a name and a job title, and an exam that is nearly
agent-independent is nearly a claim about the model rather than the agent. ADR-0051's runner says
this in its own words: an agent examined under a prompt that replaced its layers *"would be a
different agent from the one being certified"*. A prompt that never had them is a weaker version of
the same objection.

**It is not a blocker and it is a real dilution**, and the honest position is that it is stated
rather than discovered later.

### The follow-on, which is not this change

`village.db` already holds `beliefs_store_data`, `affect_ledger_data`, `self_model_data` and
`encounter_log_data`, populated for these agents — the raw material for BREATH, SOUL and episodes.
Mapping those into the remaining layers is the work that would close the gap, and it is a package
of its own with its own mapping decisions.

## What this does not decide

Whether a battery should REFUSE a snapshot-backed reader outright. The ruling asks that identity be
read from the live database and that a miss refuse; both are built. Refusing the snapshot path
entirely would also refuse every test harness, and is a separate call.

Whether `VILLAGE_DATA_PATH` should point at the real tree. It is still the 8-agent fixture, and
after this change that only affects the non-identity layers — which are missing for the real agents
either way.
