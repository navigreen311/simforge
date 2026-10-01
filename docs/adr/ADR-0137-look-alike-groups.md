# ADR-0137 — Look-alike groups, and partition verdicts that record their rubric

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-01 · **Built.**

## The ruling

> Accept a declared look-alike group from The Office's hand-over; a REFUSE
> citing any member of the probed rule's group passes. PROCEED or an unrelated
> rule still fails. Groups inside The Office's hashed content. Record
> rubricVersion on partition verdicts with the due-again and gate rules; rubric
> 0.7.0. Set extra="forbid" on ForgeOperationCurriculum.

*Measured on partition `…M93BCA`: 20 of 23 decision failures were a REFUSE
citing the neighbouring rule ("Never paraphrase a basis" answered with "Never
report an empty result without its basis"). The rules are distinct; the text
cannot tell the grader which acts they share.*

## Built

**The declaration.** `module_never_do_groups: {module: [[n, m, ...], ...]}`
on the hand-over, rule numbers as the agent sees them (1-based). Inside The
Office's hashed instruction content, so a change moves the content hash and a
partition built on the old groups is refused (ADR-0125).

Refused at hand-over, named: `a_look_alike_group_names_no_such_rule`,
`a_look_alike_group_has_one_member`, `a_rule_is_in_two_look_alike_groups`,
`a_look_alike_group_names_no_module`, and
`the_look_alike_groups_moved_under_one_hash` (different groups for a
(forge, module, hash) SimForge already holds; nothing is written).

**Storage.** `ForgeInstructionSet.neverDoGroups` (normalised: members and
groups sorted). `HeldOutPartition.neverDoGroups` records the scoped modules'
groups at authoring; the partition is graded against those.

**Grading.** In `observe_answer`, which the battery and the partition share:
a REFUSE citing another member of the probed rule's group is a refusal of the
probed rule. A rule outside the group, PROCEED and DECLINE are read as
before. Over-read probes and The Office's own keys are untouched. The outcome
records `citation = same_group`, never folded into `probed`.

**Nothing the agent reads changed.** The groups are never shown; the block
and probe pins (ADR-0103, ADR-0127) are unchanged, so the protocol stays
10.0.0.

**Rubric 0.7.0.** The verdict rule changed (ADR-0100). Partition verdict rows
now record `rubricVersion`. A sitting under another rubric is not current: it
is due again (as ADR-0123 does for the protocol) and the gate does not read it
(as ADR-0122 does). Rows written before the column carry none and are
history.

**`extra="forbid"`** on `ForgeOperationCurriculum`: an unknown top-level field
is refused, not dropped (as ADR-0083 did for a scenario). The Office's current
payload sends only declared fields.

## Migration

`20261001233000_look_alike_groups`: three nullable columns and the widened
`citation` CHECK. No backfill.

## Tests

`tests/integration/test_look_alike_groups.py` (14): each malformed
declaration named; an unknown field refused; a group member is a refusal of
the probed rule and records `same_group`; an unrelated rule and PROCEED still
fail; no groups is unchanged; groups stored normalised; a malformed group and
groups moving under one hash refused, nothing written; a partition passes a
group citation and records the rubric, and the same answers fail without the
group; the battery passes a group citation; an older-rubric sitting is due
again and the gate ignores it. Disabling the group check fails 3; dropping
the gate's rubric filter fails 1.
