-- ADR-0120: a partition verdict says which protocol version it was sat under.
--
-- Null on rows written before this column: a version nobody recorded is not
-- guessed. Idempotent.
ALTER TABLE "HeldOutPartitionVerdict" ADD COLUMN IF NOT EXISTS "protocolVersion" TEXT;
