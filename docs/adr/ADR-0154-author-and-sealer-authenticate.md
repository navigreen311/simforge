# ADR-0154 — The author and the sealer authenticate

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-09 · **Built.**
Strengthens ADR-0113. Partly closes the backlog item "Partition author and
sealer are verified by typed name only".

## The ruling

> author_partition takes --by and --sealed-by as typed names; nothing
> checks who ran it, so the two-person rule (ADR-0113) rests on honour.
> Make author and seal authenticate as the named person (their own
> credential at a hidden prompt), refuse if the sealer is the author,
> and audit both.

## What changes

**Operators.** `PartitionOperator`: an enrolled person, a name and a scrypt
hash of a credential (n=2^14, r=8, p=1, 16-byte salt). One per name,
compared trimmed and case-folded, as ADR-0113 compares names. A credential
is at least 12 characters. It is never stored, logged, or put in an error.

**Enrolment needs a witness.** Every enrolment after the first needs an
enrolled operator, not the enrollee, to authenticate as witness. The first
has none, and its row says so (`witnessedBy` null).

**Authoring** authenticates `--by`. The partition records the enrolled
spelling and `authoredByOperatorId`.

**Sealing** authenticates `--sealed-by`, then refuses when:

- the author never authenticated (a partition from before this ADR);
- the sealer is the author, by operator id or by name.

It records `sealedByOperatorId`. A database CHECK refuses one operator id
in both columns.

**Enforced in the service**, not only the CLI. `author_partition` and
`seal_partition` take a required `credential`; no caller can skip it.

**The CLI** asks each named person for their credential at a hidden prompt
(`getpass`). It has no flag or environment variable for one. Enrolment
asks twice and refuses a mismatch.

    python -m scripts.author_partition --enrol "<name>" [--witness "<name>"]

## Audit

`PartitionOperatorEvent`, append-only: every enrol, author and seal, with
the claimed name, the operator and witness ids when known, the outcome, a
refusal code, the partition and the venture.

- A success is written in the act's own commit. A partition cannot exist
  without its record, and a seal that loses the race leaves no "done".
- A refusal is committed on its own, after discarding anything pending.
  The act leaves nothing; the attempt leaves a row.
- An unknown name and a wrong credential read the same to the caller.
  The audit row tells them apart.

## What it does not prove

That two operators are two humans. One person who controls enrolment can
enrol a second identity. Anyone with SimForge's database credentials can
write any row. This replaces "typed a name" with "knew that person's
credential, and an enrolled person vouched for them". It is a real bar,
not proof of personhood.

Tying both acts to The Office's MFA stays on the backlog.

## Existing partitions

Sealed and retired partitions keep their typed names; nothing rewrites
them. An `authoring` partition from before this ADR cannot be sealed. It
is authored again.

## Bootstrapping

Nobody is enrolled at deploy. The first operator enrols with no witness;
the second is witnessed by the first.

## Versions

None. Grading unchanged. Migration
`20261010000000_partition_operators` adds both tables and the two
columns.
