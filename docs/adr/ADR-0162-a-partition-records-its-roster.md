# ADR-0162 — A partition records its roster, from The Office's grants

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-29 · **Built.**
Resolves B102 (The Office's blocking entry). Builds the backlog item ADR-0152
left: "the grant-backed roster from The Office".

## The ruling

> B102: partition rosters from grants. Build the grant-backed roster.

## What was wrong

`partition_roster` (ADR-0152) rosters every agent with a Unit A run on a
partition module, for the venture and forge. It reads no grants, because
SimForge holds none.

Measured by The Office on 11 October, Burkham × capitalforge over Pack
0.15.2's nine modules: **7 sitters, not 6.** Gianna Horven's grant on
`statement_pull` was retired on 5 October after she failed it. Her runs on
that module still rostered her. `venture_verdict` reads the weakest sitting,
so her FAIL would fail Gate 9.5 for a venture she no longer operates in.
Scoping `statement_pull` out with `--modules` would also drop Ivy Varos, who
does hold it. Burkham's CapitalForge partition is not authored until this is
fixed.

## The rule now

- **`author_partition` accepts a roster** (`roster=`, CLI `--roster
  <file>`): The Office's statement of its live grants for the venture and
  forge (`docs/contracts/partition-roster.md`). The operator hands it over.
  Authoring stays off HTTP (ADR-0109), and The Office still never authors
  (ADR-0108 R1).
- **It is recorded on the partition.** `HeldOutPartition.roster` holds the
  in-scope grants, sorted, plus `stated_at`. `rosterDigest` holds the sha256
  of that roster. A grant on a module outside the partition is dropped. A
  statement for another venture or forge, a repeated grant id, an unknown
  key, or no in-scope grant is refused, and nothing is written.
- **The seal binds it.** `contentDigest` becomes the sha256 over the sorted
  scenario digests plus one more line, `roster:<rosterDigest>`. Sealing
  re-hashes the roster first and refuses one that moved since authoring
  (`roster_changed_since_authoring`, audited).
- **`partition_roster` returns the recorded roster when there is one.** The
  agents are the grants' agents, each with its granted modules, and no run
  is read. So a retired grant's agent is not rostered, however many runs it
  has. The grader and `venture_verdict` both read it, as ADR-0152 requires.
- **After the seal**, the grader recomputes `contentDigest` from the stored
  scenarios and roster before putting anything. A mismatch is skipped
  (`the_partition_no_longer_matches_its_seal`) and nothing is written.
  `venture_verdict` may not read scenarios (the router import-graph guard),
  so it re-hashes the roster alone and answers NOT_RUN on a mismatch.
- **Older partitions are unchanged.** With no roster, both new columns are
  null, the roster is ADR-0152's, and `contentDigest` is computed exactly as
  before. Every partition sealed before this ADR still verifies.

## How it is stamped

By the partition's own row, not by a version:

- **`rosterDigest` non-null means grant-backed.** It is set once, at
  authoring, and the seal folds it into `contentDigest`. Null means the
  ADR-0152 roster.
- `contentDigest` takes the new form only when `rosterDigest` is set. So the
  form of a partition's digest is decided by its own row, the way
  `verdictRule` decides its verdict rule (ADR-0143).
- **No version moves.** Protocol (`PARTITION_PROTOCOL_VERSION`) and rubric
  are unchanged: no probe is built differently, no answer is read
  differently, and no verdict means something else. The roster changes who
  is put the questions, and the row records that.

## Isolation

`partition_roster` still reads `OperationRun` and the partition row only, and
never `HeldOutPartitionScenario`. The digest check that needs the scenarios
lives in the grader, which already reads them.
`test_no_router_can_reach_the_scenarios` is unchanged and passes.

## What The Office must do

At authoring, export its live grants (`agent_forge_grant`, `revoked_at IS
NULL`) for the venture and forge, as the contract's JSON, with `agent_id` set
to the Village ref. The operator passes the file with `--roster`.

## Versions

- No protocol or rubric bump (above).
- Migration `20261029000000_a_partition_records_its_roster` adds `roster`
  (JSONB) and `rosterDigest` (TEXT) to `HeldOutPartition`. Nothing is
  backfilled.

## Tests

`tests/integration/test_a_partition_rosters_its_grants.py`:

- authoring records the in-scope grants, sorted, with their digest; each
  refusal writes nothing;
- the seal folds the roster into `contentDigest`, and the same scenarios
  without it digest differently; a roster changed before the seal is
  refused and audited;
- **a retired agent is not rostered.** It has runs on the module and no
  grant, so the sweep writes it no row, and a FAIL under the same seal does
  not hold the gate. Control: a rostered agent's FAIL still does;
- a roster edited after the seal is not graded and the verdict reads
  NOT_RUN; a roster rewritten together with its digest is still not graded;
- **older partitions are unchanged:** no roster seals to the old digest, and
  run history still rosters, retired agent included;
- the CLI reads a roster file and prints only a count; the migration adds
  both columns and backfills nothing.
