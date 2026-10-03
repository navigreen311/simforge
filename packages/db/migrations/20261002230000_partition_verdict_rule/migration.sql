-- ADR-0143: Gate 9.5 tolerates one slip per agent on partitions sealed under rule 2.
--
-- HeldOutPartition.verdictRule      - stamped at seal. Null is rule 1, zero tolerance:
--                                     every partition sealed before ADR-0143.
-- HeldOutPartitionVerdict.slipCount - a sitting's slips when every FAIL in it is one.
--                                     Null when any FAIL is hard, and on older rows.
-- Nothing backfilled. Idempotent.
ALTER TABLE "HeldOutPartition" ADD COLUMN IF NOT EXISTS "verdictRule" INTEGER;
ALTER TABLE "HeldOutPartition"
    DROP CONSTRAINT IF EXISTS "held_out_partition_verdict_rule";
ALTER TABLE "HeldOutPartition"
    ADD CONSTRAINT "held_out_partition_verdict_rule"
    CHECK ("verdictRule" IS NULL OR "verdictRule" IN (1, 2));

ALTER TABLE "HeldOutPartitionVerdict" ADD COLUMN IF NOT EXISTS "slipCount" INTEGER;
ALTER TABLE "HeldOutPartitionVerdict"
    DROP CONSTRAINT IF EXISTS "held_out_partition_verdict_slip_count";
ALTER TABLE "HeldOutPartitionVerdict"
    ADD CONSTRAINT "held_out_partition_verdict_slip_count"
    CHECK ("slipCount" IS NULL OR "slipCount" >= 0);
