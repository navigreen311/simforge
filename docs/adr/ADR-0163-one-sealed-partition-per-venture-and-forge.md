# ADR-0163 — One sealed partition per venture and forge

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-29 · **Built.**
Resolves B96 (The Office's blocking entry). Narrows ADR-0113 ruling 2, the
retire rule of ADR-0109, and ADR-0108 R4's "the currently sealed partition".
Builds Gate 9.5 contract v2, approved in principle on 11 October.

## The ruling

> B96: build the venture x forge fix as you proposed: index swap,
> `_retire_sealed` scoped to forge, `_lost_the_race` on the new index,
> Gate 9.5 optional `forge_id` (with it: that Forge, plus `forge_id` and
> `partition_id`; without it: four keys, weakest across the venture's sealed
> partitions).

## What was wrong

A partition belongs to a venture and a forge (`HeldOutPartition.forgeId`).
The seal belonged to the venture alone:

- `_retire_sealed(session, venture_id, keep=...)` retired every other sealed
  partition of the venture, whatever its forge.
- `HeldOutPartition_one_sealed_per_venture` was unique on `ventureId` where
  `status = 'sealed'`.
- `venture_verdict` read the venture's newest seal, `LIMIT 1`.

Nobody chose that scope. ADR-0109's seal rule was written when a venture ran
one forge. ADR-0113 ruling 2 fixed a race and made the rule a unique index.

Measured on the dev database, counts only: Burkham's FunnelForge seal on
10 October retired its CapitalForge partition. The CapitalForge seal on
11 October retired FunnelForge's in turn. Run 432f629a (Pack 0.15.2, no
FunnelForge) was blocked at Gate 9.5 by the FunnelForge partition, the only
one sealed at the time.

## The rule now

- **The database holds one sealed partition per venture and forge.** A new
  unique partial index, `HeldOutPartition_one_sealed_per_venture_forge`, on
  `(ventureId, forgeId) WHERE status = 'sealed'`, replaces the old index.
  Two seals of one forge that race still lose at the second commit. Two
  forges do not race each other.
- **A seal retires only its own forge's earlier seal.**
  `_retire_sealed(session, venture_id, forge_id, keep=...)` adds the forge to
  the filter. The retirement, the seal and the seal's audit record are still
  one commit, and `retiredPartitionIds` still lists what was retired.
- **`_lost_the_race` knows both index names**, the new one and ADR-0113's,
  so a database not yet migrated still reports a lost race as one.
- **Gate 9.5 takes an optional `forge_id`** (`docs/contracts/gate-9-5-verdict.md`):
  - **With it (v2)**: that forge's sealed partition, by the same rules as
    before. The answer is six keys: the four, plus `forge_id` (echoed) and
    `partition_id`. These are identifiers only. `partition_id` is null if and
    only if `partition_exists` is false.
  - **Without it (v1)**: the four keys, unchanged. With several forges
    sealed, the answer is the weakest across them (FAIL < TIMEOUT <
    IN_PROGRESS < NOT_RUN < PASS; among equals, the latest decision). It is
    never more lenient than any one forge. A venture with one sealed
    partition, which is every venture today, reads exactly as before.
  - The extra keys appear only when `forge_id` is sent. The Office's
    manifest refuses a fifth key, so a v1 caller cannot be broken by this.

## What does not change

- **The grader, the sweep and the re-sit** take a partition by id, or every
  sealed partition, and never "the" venture's. They needed no change.
- **`partition_roster`** was already venture and forge. A recorded roster
  (ADR-0162) binds its own partition, so each forge is read by its own: a
  roster that no longer holds makes that forge NOT_RUN, and v1 reads it as
  the weaker.
- **No partition is un-retired.** Retired is final and no record is
  rewritten. The migration has no `UPDATE`. The partitions retired by the
  other forge's seal on 10 and 11 October stay retired, the seal records
  still name them, and their verdict rows are still not read. A forge whose
  partition was retired that way gets one back only by authoring and sealing
  a new one.
- **No protocol or rubric bump.** No probe is built or graded differently.
  The change is which partitions may be sealed at once, and which one a
  question reads.

## What The Office must do

Update its manifest for the v2 shape first. Then, at Gate 9.5, ask once per
forge the run binds, record `forge_id` and `partition_id` in its evidence,
and refuse an answer about a forge the run does not bind. Until then, its v1
call is answered as before, with the weakest across forges, so another
forge's FAIL still blocks it.

## Versions

- Migration `20261029120000_one_sealed_per_venture_and_forge`: builds the new
  index, then drops the old one, so neither moment is unguarded. Every row
  that satisfies the old index satisfies the new one.
- No protocol or rubric bump (above).

## Tests

`tests/integration/test_one_sealed_per_venture_and_forge.py`:

- two forges stay sealed side by side, and the second seal retires nothing;
- a reseal retires its own forge's earlier seal and leaves the other forge's
  sealed;
- the database refuses a second sealed partition for one venture and forge,
  and `_lost_the_race` recognises the refusal; a lost race for one forge is
  refused and leaves the loser in `authoring`;
- the migration builds the new index before dropping the old, and rewrites
  nothing;
- each forge is read by its own recorded roster (ADR-0162);
- Gate 9.5 v2 reads one forge with six keys, and another forge's FAIL is not
  read; v1 reads four keys, the weakest across forges; a venture with one
  sealed partition answers v1 exactly as before; an unknown or retired forge
  reads as absent; a malformed v2 body is a 422.

`tests/contract/test_gate_9_5_verdict_contract.py` holds the v2 keys against
the page.
