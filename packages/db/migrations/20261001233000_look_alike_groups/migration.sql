-- ADR-0137: look-alike groups, and partition verdicts that record their rubric.
--
-- ForgeInstructionSet.neverDoGroups  - the groups The Office declared, rule numbers 1-based.
-- HeldOutPartition.neverDoGroups     - the groups a partition was authored with.
-- HeldOutPartitionVerdict.rubricVersion - the rubric a sitting was graded under. Null on rows
--   written before: not current, so the gate ignores them and the grader re-sits them.
-- HeldOutPartitionOutcome.citation gains 'same_group'.
-- Nothing is backfilled. Idempotent.
ALTER TABLE "ForgeInstructionSet" ADD COLUMN IF NOT EXISTS "neverDoGroups" JSONB;
ALTER TABLE "HeldOutPartition" ADD COLUMN IF NOT EXISTS "neverDoGroups" JSONB;
ALTER TABLE "HeldOutPartitionVerdict" ADD COLUMN IF NOT EXISTS "rubricVersion" TEXT;

ALTER TABLE "HeldOutPartitionOutcome"
    DROP CONSTRAINT IF EXISTS "held_out_partition_outcome_citation";
ALTER TABLE "HeldOutPartitionOutcome"
    ADD CONSTRAINT "held_out_partition_outcome_citation"
    CHECK ("citation" IS NULL OR "citation" IN ('probed', 'same_group', 'other', 'none', 'out_of_range'));
