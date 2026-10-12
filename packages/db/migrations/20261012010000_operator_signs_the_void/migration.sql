-- ADR-0159: the practice-run void (ADR-0158) is signed by an enrolled
-- operator, who authenticates with their own credential (ADR-0154).
--
-- PartitionOperatorEvent gains the act 'void'. Every attempt is recorded,
-- refusals included. No new column. Idempotent.
ALTER TABLE "PartitionOperatorEvent" DROP CONSTRAINT IF EXISTS "partition_operator_event_act";
ALTER TABLE "PartitionOperatorEvent" ADD CONSTRAINT "partition_operator_event_act"
    CHECK ("act" IN ('enrol', 'author', 'seal', 'reset', 'void'));
