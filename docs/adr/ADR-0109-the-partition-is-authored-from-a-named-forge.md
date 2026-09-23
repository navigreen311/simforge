# ADR-0109 — The partition is authored from a named forge, and sealed once

**Status:** accepted · **Date:** 2026-09-23 · **Follows:** ADR-0108 (R1–R3)
**Built:** `apps/api/src/services/operation/held_out_partition.py`,
`apps/api/scripts/author_partition.py`

---

## R3, measured

ADR-0108 R3 says a venture's scope is its forge's current
`ForgeInstructionSet` modules. The question left was how a venture
reaches its forge. Measured on main at e690d91:

- `Venture` has `slug` and `internalForges`, a free-form string list.
  The seed registry gives one venture two forges
  (`["medlink-pro", "vaf"]`). Nothing compares these strings to
  `ForgeInstructionSet.forgeId`.
- `ForgeInstructionSet` has `forgeId` and `moduleId`. No venture column.
- `OperationRun.runRef` is an opaque unique string. It carries no
  venture.
- A Unit B certification request carries `venture_context` beside
  `forge_id`, stored as `OperationCertification.ventureContext`. That
  pairs a venture and a forge per request, for one certification. It is
  not a registry: nothing says it is the venture's only forge, or that
  it is current.
- The Office's venture id reaches SimForge only as the
  `X-Office-Venture` header on the bridge. It is logged, never joined,
  and is not a `Venture.slug`.

**There is no mapping.** So `author_partition` takes `forge_id`
explicitly beside `venture_id`, and the operator names both. A partition
row records both. Guessing a forge from `internalForges` would pick one
of several free-form strings and call the pick a fact.

"Current" is measured too: `ForgeInstructionSet` keeps one row per
content hash, several per module. The current set of a module is its
newest row by `createdAt` (ties by id). A module whose current set has
an empty `neverDo` contributes nothing.

## What is built

**Author.** `author_partition(session, venture_id, forge_id, authored_by)`:

1. Reads the forge's current never-do list per module.
2. Runs the ordinary pipeline, `held_out.author_for_modules`, on it.
3. For every scenario it yields, writes three **adversarial variants**:
   `reworded`, `indirect`, `pressure`. Same class, same obligation, same
   grading key. Only `probe` changes, and it keeps the ADR-0094 naming
   sentences so the shape of a probe gives nothing away.
4. Which wording each variant takes is chosen by
   `sha256(seed | class | ref | framing)`. **The seed is the partition's
   own id.** It is recorded by the row that uses it, and nobody can know
   it before the row exists. `adversarial_variants(never_do, id)`
   reproduces the stored digests exactly.
5. Refuses, writing nothing, if any variant's digest equals a battery
   digest, if any probe is word-for-word a battery probe, or if two
   variants share a digest (R2).
6. Writes `HeldOutPartition(status="authoring")` and one
   `HeldOutPartitionScenario` per variant, and commits.

It also refuses a blank argument, a forge with no never-do list, and an
`authored_by` that names The Office (R1).

**The seam.** `body` is exactly the fields of `HeldOutScenario`,
tuples as lists. `HeldOutScenario(**body)` with `unsupported_readings`
re-tupled rebuilds it (`scenario_from_body`).
`digest = sha256(json.dumps(body, sort_keys=True, separators=(",",":")))`,
hex, no prefix.

**Seal.** `seal_partition(session, partition_id)`:

- only an `authoring` partition; an empty one is refused;
- `contentDigest = sha256("\n".join(sorted(scenario digests)))`, hex;
- `status = "sealed"`, `sealedAt = now`;
- every other `sealed` partition of the same venture becomes `retired`,
  in the same commit.

**The operator CLI.** `python -m scripts.author_partition --venture V
--forge F --by NAME [--seal]`, or `--seal-id ID`. It prints the id, a
count and the digest. Never a scenario.

## What keeps it out of an exam

No route authors or reads a partition. The unit test walks the static
import graph from every module under `src/routers`, and from the
battery and curriculum path (`battery`, `battery_result`, `scenarios`,
`held_out`, `held_out_scoring`, `never_do`, `run_registry`,
`operation_payloads`). None may reach `held_out_partition`. Both import
spellings are covered, with a negative control.

## Tests assert rows, not returns

Integration tests run each call in its own session, close it, and read
back from a fresh one. A negative control shows a flush without commit
reads back empty, so a function that returns an id and writes nothing
fails.

## What this does not do

- It does not grade a partition or record a verdict (ADR-0110).
- It does not answer The Office (ADR-0111).
- It does not map a venture to a forge. That needs a real mapping,
  and a later ADR.
- It does not enforce separation of duties between author and sealer.
  `authoredBy` records who triggered it (ADR-0108 R1).
- Two seals racing for one venture could both land `sealed`. Sealing is
  an operator act from one CLI; a unique partial index would close it
  and is a migration, not this change.
