-- ADR-0128: a partition records the protocol version its probes were built under,
-- and is not graded under another.
--
-- Not backfilled. A partition authored before this column stores bodies from a
-- builder nobody recorded; guessing its version would label old questions with a
-- new number. Null is refused by the grader. Idempotent.
ALTER TABLE "HeldOutPartition" ADD COLUMN IF NOT EXISTS "protocolVersion" TEXT;
