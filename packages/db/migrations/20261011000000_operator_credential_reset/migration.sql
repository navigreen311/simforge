-- ADR-0156: a lost operator credential is reset, witnessed.
--
-- The reset replaces PartitionOperator."credentialHash" in place; the
-- operator keeps their id, so no partition or event is rewritten. No new
-- column. PartitionOperatorEvent gains the act 'reset' and the outcome
-- 'witnessed' (the witness authenticated; the reset's first step).
-- Idempotent.
ALTER TABLE "PartitionOperatorEvent" DROP CONSTRAINT IF EXISTS "partition_operator_event_act";
ALTER TABLE "PartitionOperatorEvent" ADD CONSTRAINT "partition_operator_event_act"
    CHECK ("act" IN ('enrol', 'author', 'seal', 'reset'));
ALTER TABLE "PartitionOperatorEvent" DROP CONSTRAINT IF EXISTS "partition_operator_event_outcome";
ALTER TABLE "PartitionOperatorEvent" ADD CONSTRAINT "partition_operator_event_outcome"
    CHECK ("outcome" IN ('done', 'refused', 'witnessed'));
