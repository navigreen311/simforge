-- ADR-0124: a readable answer records the act it chose, as codes only.
--
-- chosenAct, citation, citedRule and recordKind on every readable outcome.
-- Null on an unreadable answer (its shape is recorded instead) and on rows
-- written before. Never text. Idempotent.
ALTER TABLE "HeldOutPartitionOutcome" ADD COLUMN IF NOT EXISTS "chosenAct" TEXT;
ALTER TABLE "HeldOutPartitionOutcome" ADD COLUMN IF NOT EXISTS "citation" TEXT;
ALTER TABLE "HeldOutPartitionOutcome" ADD COLUMN IF NOT EXISTS "citedRule" INTEGER;
ALTER TABLE "HeldOutPartitionOutcome" ADD COLUMN IF NOT EXISTS "recordKind" TEXT;

ALTER TABLE "HeldOutPartitionOutcome"
    DROP CONSTRAINT IF EXISTS "held_out_partition_outcome_chosen_act";
ALTER TABLE "HeldOutPartitionOutcome"
    ADD CONSTRAINT "held_out_partition_outcome_chosen_act"
    CHECK ("chosenAct" IS NULL OR "chosenAct" IN ('PROCEED', 'REFUSE', 'DECLINE', 'ESCALATE'));
ALTER TABLE "HeldOutPartitionOutcome"
    DROP CONSTRAINT IF EXISTS "held_out_partition_outcome_citation";
ALTER TABLE "HeldOutPartitionOutcome"
    ADD CONSTRAINT "held_out_partition_outcome_citation"
    CHECK ("citation" IS NULL OR "citation" IN ('probed', 'other', 'none', 'out_of_range'));
ALTER TABLE "HeldOutPartitionOutcome"
    DROP CONSTRAINT IF EXISTS "held_out_partition_outcome_record_kind";
ALTER TABLE "HeldOutPartitionOutcome"
    ADD CONSTRAINT "held_out_partition_outcome_record_kind"
    CHECK ("recordKind" IS NULL OR "recordKind" IN ('NONE', 'CLAIM'));
