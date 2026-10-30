# Partition roster: what The Office states at authoring

SimForge names this. Decided and built in ADR-0162 (B102).

A held-out partition is sat by the agents The Office says hold live grants
on its modules. The Office writes the statement. The operator who authors the
partition hands it to SimForge. SimForge records it on the partition and the
seal binds it.

## How it arrives

Not over HTTP. No route authors or reads a partition (ADR-0109). The
statement is a JSON file, passed to the operator CLI:

    apps/api/.venv/Scripts/python.exe -m scripts.author_partition \
        --venture <venture_id> --forge <forge_id> --by "<author>" \
        [--modules a,b] --roster <statement.json>

The CLI prints `rostered_agents`, a count. It never prints the roster.

## The statement

    {
      "venture_id": "<the partition's venture>",
      "forge_id":   "<the partition's forge>",
      "stated_at":  "<ISO 8601, when The Office read its grants>",
      "grants": [
        {
          "grant_id":  "<agent_forge_grant.grant_id>",
          "agent_id":  "<the Village agent ref>",
          "module_id": "<the granted module>"
        }
      ]
    }

- **Live grants only,** as The Office states it (`broker/revocation.py`,
  `live_grant`): grants for this venture and forge that are **not superseded**
  (`superseded_at IS NULL`) and **not covered by a live revocation** (no
  `revocation` row whose agent, forge, module or venture scope covers the
  grant). `agent_forge_grant` has no `revoked_at`; The Office dropped it in
  its migration 0036. SimForge holds no grants and cannot tell a retired one
  from a live one, so a grant listed here is a sitter.
- **A grant created but not yet activated counts.** Gate 9.5 runs before
  Gate 11 activates grants, so at authoring the agents about to operate the
  modules hold grants that are not yet active. List them.
- **`agent_id` is the Village agent ref**, the id a probe is put to
  (ADR-0083: `villageAgentRef`, else `agentId`). It is not
  `office_agent_id`.
- Any other key, at either level, is refused (`extra: forbid`).
- `stated_at` is recorded and never compared.

## What SimForge records

`HeldOutPartition.roster`:

    {"stated_at": "...", "grants": [{"grant_id", "agent_id", "module_id"}, ...]}

- **In-scope grants only.** A grant on a module the partition does not cover
  is dropped, because there is nothing to put to it (ADR-0152). The scope is
  `--modules` when given. Otherwise it is every module with a live never-do
  list.
- The grants are trimmed and sorted by agent, then module, then grant, so
  one set of grants is always recorded the same way.

`HeldOutPartition.rosterDigest` is the sha256 (hex) of the recorded roster's
canonical JSON (sorted keys, no spaces).

## Refusals

A refused statement writes nothing: no partition and no scenarios. The CLI
exits 2 with `refused: <message> (<code>)`.

| code | when |
|---|---|
| `roster_statement_invalid` | the shape above is broken, or a key is unknown |
| `roster_names_another_venture_or_forge` | `venture_id` or `forge_id` is not the partition's |
| `roster_repeats_a_grant` | two grants share a `grant_id` |
| `roster_sits_nobody` | no grant is on a module the partition covers |

## The seal

    contentDigest = sha256( sorted(scenario digests) + ["roster:" + rosterDigest] ), newline-joined

The roster line comes after the sorted scenario digests. A scenario digest is
bare hex and never holds a colon, so no scenario can be mistaken for it.

- **Before sealing**, the roster is re-hashed. If it no longer matches
  `rosterDigest`, the seal is refused (`roster_changed_since_authoring`,
  audited) and the partition stays in `authoring`.
- **Before grading**, the grader recomputes the whole digest from the stored
  scenarios and roster. If it does not match `contentDigest`, nothing is put
  (`the_partition_no_longer_matches_its_seal`).
- **The verdict** (`venture_verdict`) reads no scenarios. It re-hashes the
  roster alone, and answers `NOT_RUN` (`decided_at` null) when the roster no
  longer matches `rosterDigest`.

## Who sits, and who counts

The grader puts the partition to the roster's agents. Each agent is put only
its granted modules. `venture_verdict` reads rows for those agents only. Run
history is not consulted, so an agent with runs on the modules and no live
grant is not rostered. Its rows, old or new, are not read.

## A partition without a roster

`roster` and `rosterDigest` are null. Its roster is ADR-0152's (run history,
scoped to its modules). Its `contentDigest` is the scenario digests alone,
exactly as before. Every partition authored before ADR-0162 is one of these.
