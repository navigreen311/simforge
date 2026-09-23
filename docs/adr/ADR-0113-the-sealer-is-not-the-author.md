# ADR-0113 — A partition's sealer is never its author, and the database holds one seal per venture

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-23 · **Built.**

---

## The rulings

> **1.** A partition's sealer is never its author. Both are named humans.
> Sealing writes its own audit record.
> *Measured: nothing checks it, and the partition is the one exam an
> agent cannot have seen.*

> **2.** One sealed partition per venture, enforced by the database.
> Unique index.
> *Measured: two seals racing could both seal.*

Both were open gaps in ADR-0109.

## What let it through

- `seal_partition(session, partition_id)` took no sealer at all.
  `authoredBy` was the only name on a partition.
- The CLI's `--seal` authored and sealed in one invocation, by one person.
- One-sealed-per-venture was a retire-then-seal in one commit.
  Two sessions could each retire nothing and each seal.

## Built

### Ruling 1

- `HeldOutPartition.sealedBy`. `seal_partition(session, pid, sealed_by)`.
- `named_human()` refuses blank, The Office, and a process, role or
  placeholder (`system`, `simforge`, `ops`, `admin`, ...). It applies to
  the author and the sealer.
  **ASSUMPTION:** SimForge has no registry of people, so this is a
  deny-list, not proof of personhood. A people registry replaces it.
- Author and sealer compared trimmed and case-folded, in Python and in SQL.
- Two CHECKs on `HeldOutPartition`:
  - `held_out_partition_sealer_is_not_author`
  - `held_out_partition_seal_names_sealer`: past `authoring`, `sealedBy` is set.
- `HeldOutPartitionSeal`: the seal's own audit record. Append-only, one
  per partition. It names the author, the sealer, the content digest, and
  the partitions the seal retired. It is written in the same commit as the
  seal, and has its own CHECK that its two names differ.
- The CLI now takes two commands: `--by` to author, then
  `--seal-id ... --sealed-by ...` to seal. `--seal` is gone.

### Ruling 2

- `HeldOutPartition_one_sealed_per_venture`: a unique partial index on
  `ventureId` where `status = 'sealed'`. It is migration-only in Prisma,
  and mirrored in SQLAlchemy so the suite enforces it too.
- A seal that loses the race is refused by name ("another seal ...
  committed first") and leaves nothing behind: no seal, no audit record.
  Any other constraint failure is named as a database refusal, not as a
  race.

## Applied to the dev DB

The dev DB's `_prisma_migrations` records only `init`. Every later
migration was applied by running its SQL, so `prisma migrate deploy`
would try to replay all of them. These two were applied the same way:

- `20260923120000_the_held_out_partition` (ADR-0108, not yet applied)
- `20260923200000_the_sealer_is_not_the_author`

Confirmed afterwards: all four tables, `sealedBy`, the partial index
and the three new CHECKs. All four tables hold 0 rows.

Then probed live, each attempt in a transaction rolled back:

| Attempt | Postgres |
|---|---|
| author seals own (` ivan green `) | `held_out_partition_sealer_is_not_author` |
| sealed, no sealer | `held_out_partition_seal_names_sealer` |
| two sealed, one venture | `HeldOutPartition_one_sealed_per_venture` |
| control: one sealed, one retired | accepted |

## Tested

`tests/integration/test_the_sealer_is_not_the_author.py`, 23 tests.
Every assertion reads back from a fresh session.

- An author sealing (three spellings) is refused and writes nothing.
- A sealer or author who is no person is refused.
- The audit record matches the sealed row, including the retired id.
- The database refuses: the author as sealer, a seal with no sealer, and
  an audit record with one person twice.
- Two sealed partitions for one venture fail. Other ventures and retired
  rows are not limited.
- Losing the race is refused, and the loser stays `authoring` with no
  audit record.
- Mutations: dropping the audit write fails 2 tests; dropping the
  service's author check fails 3.

The fixtures of ADR-0110 and ADR-0111 now name a sealer on sealed rows.

## What this does not do

- It does not prove a name belongs to a person.
- It does not make The Office aware of who sealed. The verdict stays
  whether, never why.
