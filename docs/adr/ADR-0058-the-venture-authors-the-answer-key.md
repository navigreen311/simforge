# ADR-0058 — The venture authors the answer key; SimForge grades it

**Status:** accepted · **Decided by:** Ivan Green, 17 September 2026
**Scope:** the certification relationship between a venture, The Office and SimForge.
**Supersedes nothing. Names the rule that ADR-0048, ADR-0049 and ADR-0050 were each one half of.**

---

## The rulings

**1. Every venture's agents are certified through SimForge, against an answer key per module:
what the agent should do, and when it must stop and get a human.**

**2. The venture authors the answer key; SimForge grades it. SimForge never grades content it
wrote itself, except its own held-out classes.**

**3. Gate 9.5's held-out adversarial test lives only in SimForge and is never visible to The
Office. It is written by the founder who did not approve that venture's training content.**

Recorded together because they are one rule about authorship seen from three distances: per
module, per system, and per person.

## What already conforms, verified rather than assumed

**The answer key is the shape the payload already has.** `OperationScenarioSubmission` carries
`expected_behavior` and `expected_escalation` on every scenario, and those two fields are ruling 1
in the wire format: what the agent should do, and when it must stop and get a human. Nothing needs
inventing for the key to exist — it exists, and this ADR names what it is for.

**Ruling 2's exception is already the line ADR-0048 drew.** A submitter may not author a
`never_do_violation` scenario; `HELD_OUT_CLASSES` is `{never_do_violation, silent_failure}` and
`classify_certification_level` strikes a submitter's declarations for both before they count, so
"an Office submission can supply at most seven of nine" is enforced rather than stated. ADR-0050
adds the other side of the same rule: no credential fetches the held-out set, so the battery runs
in-process and there is no route by which a submitter could read what it is graded on.

## What does NOT conform today, and it is not a small list

**Nothing in the operation path is keyed by venture.** `ForgeInstructionSet`, `OperationRun` and
the Unit-A half of `OperationCertification` carry no venture column. The Office's `mint_run_ref`
puts `venture_id` in the ref's second segment, so the fact reaches SimForge on every run and is
stored only as an unparsed prefix of an opaque string. Two ventures operating a same-named module
on one Forge are, in this database, one module. The full enumeration is in the accompanying report
rather than here, because it is a survey and not a decision.

**One consequence is live, today, on one Forge.** Two `capital-forge/statement_ingest` rows exist —
`1.2.0` seeded by hand on 21 August with `['overwrite_prior_statement']`, and `1.0.0` written
through the Office bridge on 7 September with `['never post to the ledger']`.
`module_never_do_lists` scans every instruction set in no declared order and keeps the first that
carries a list; `battery_for_run` picks its instruction set by `createdAt DESC`. **Those are two
different selection rules over the same ambiguity**, and on the live data they select different
rows: a battery would author its probes from the August list and bind the certification to the
September row. Not a venture collision yet — one venture, two rows — but it is the same mechanism,
and it is already wrong.

**Four of the five live instruction sets were authored inside SimForge, not submitted by a
venture.** `authoredBy` reads `ivan` on four rows and `office` on one. Under ruling 2 the four are
not answer keys a venture wrote; they are seeds, and a battery grading against them is SimForge
grading content its own side authored. They predate the rule and this ADR does not void them — it
names them, so that "certified" against a seed is never read as "certified" against a curriculum.

**Gate 9.5 does not exist on either side.** The Office half is built and honest about it:
`_gate_9_5` calls a one-method port, whose only implementation, `PartitionAbsent`, returns `None`
and **blocks every provisioning run** with `held_out_partition_not_created`. SimForge authors
held-out scenarios per module from a declared never-do list; it has no per-venture adversarial set,
no record of who authored one, and no verdict endpoint. Ruling 3 additionally requires an
authorship fact neither system holds: which founder approved a venture's training content, and
that a different one wrote its adversarial set.

## Why ruling 3 is the one that needs a new mechanism rather than a new column

Rulings 1 and 2 are about where content comes from, and both systems already route content by
origin. Ruling 3 is about **separation of duties between two people**, and neither side has a
person in this path. The Office has `office_human` and a `gate_10` sign-off bound to an artifact
hash, which is the closest existing thing; SimForge has no human registry at all. A per-venture
held-out set therefore needs an author identity, a record of the approver it must differ from, and
a check between them — and the check has to be computable by the side that holds the set, which is
SimForge, from a fact that originates in The Office.

**That is a port, not a field**, and it is the reason ruling 3 is sized separately and not built
here.

## What this ADR does not decide

Whether the four hand-seeded instruction sets are retired, re-submitted or left standing. Whether
a venture column is added by migration or a run's venture is parsed out of its ref. What a
per-venture held-out set contains. Each is its own decision with its own cost, and folding them
into a ruling about authorship would be deciding them by implication.
