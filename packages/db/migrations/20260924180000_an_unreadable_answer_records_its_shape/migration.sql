-- ADR-0118: an unreadable answer records its shape, as codes only.
--
-- The line sequence (ACT, RECORD, CAVEAT, OTHER) and the set of act words
-- that appeared. Null on a readable answer. Never text. Idempotent.
ALTER TABLE "HeldOutPartitionOutcome" ADD COLUMN IF NOT EXISTS "answerShape" JSONB;
ALTER TABLE "HeldOutPartitionOutcome" ADD COLUMN IF NOT EXISTS "actWords" JSONB;
