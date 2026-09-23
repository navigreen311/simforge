# ADR-0108 — The held-out partition is SimForge's, and The Office learns whether

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-23 · **Contract only.**

---

## The problem

The Office cannot certify an agent against scenarios it wrote itself.
Gate 9.5 exists so an agent faces scenarios it has never seen.
The Office's port is `HeldOutSource.verdict(venture_id) -> str | None`.
Its one implementation, `PartitionAbsent`, returns `None`. Every run blocks.

## What was measured

- SimForge's held-out probes are authored per module from `neverDo`.
  They are deterministic, rebuilt every exam, and never stored.
  The Office cannot see them. The agent sees them every time.
  **They are not the partition.**
- Nothing in the operation path is keyed by venture (ADR-0058).
- No document on either side names a Gate 9.5 response shape.

## The questions, answered by measurement

1. **Certification or signature?** The signature.
   9.5 sits between Gate 9 (certification) and Gate 10 (signature).
   It writes no certification row. SimForge's operation path signs nothing.
   *Measured: theoffice `broker/provisioning.py` GATE_SEQUENCE, `_gate_9_5`.*
2. **Absent or failing?** Both block. Neither is skipped.
   Absent reads "at ceiling". Non-PASS reads "stopped at gate 9.5".
   *Measured: `provisioning.py:2473-2508`, `:3553-3588`.*
3. **Simulation?** It cannot pass today, and it should not.
   A simulated pass would lead straight to Gate 10's signature.
   A default is not evidence (ADR-0106).
   SimForge stays blind to simulation. The Office's gate holds the rule.

## The rulings

> **R1.** SimForge authors the partition. `authoredBy` records who
> triggered and sealed it. Never The Office. Separation of duties
> between founders (ADR-0058 ruling 3) is a later ADR.

> **R2.** The partition is a separate set, disjoint by digest from
> the ordinary battery's held-out probes. It is never put to an agent
> in the ordinary battery.

> **R3.** A venture's scope is its forge's current `ForgeInstructionSet`
> modules. ADR-0109 records the measurement.

> **R4.** One verdict per venture: the weakest agent's latest verdict
> on the currently sealed partition.

> **R5.** The response shape is `docs/contracts/gate-9-5-verdict.md`.
> Four keys, always. SimForge names it; The Office records it.

## Built here

- `HeldOutPartition`, `HeldOutPartitionScenario`, `HeldOutPartitionVerdict`:
  Prisma, SQLAlchemy mirror, migration `20260923120000_the_held_out_partition`.
  Append-only. No reason column anywhere.
- `docs/contracts/gate-9-5-verdict.md`.

## Built after, in parallel

- ADR-0109: author and seal (`held_out_partition.py`).
- ADR-0110: grade, record whether (`partition_grading.py`, `partition_sweep.py`).
- ADR-0111: the verdict endpoint (`partition_verdict.py`, bridge module).

## What this does not do

- It does not touch The Office. Its adapter comes after, against the page.
- It does not change `office-simforge-contract.json`.
- It does not change the ordinary battery or its held-out probes.
