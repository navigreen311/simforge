-- ADR-0121: a sitting is three seeds, and every row records its seed.
--
-- Null on rows written before these columns: the seed was 0 then, but a
-- value nobody recorded is not backfilled. Idempotent.
ALTER TABLE "HeldOutPartitionVerdict" ADD COLUMN IF NOT EXISTS "seed" INTEGER;
ALTER TABLE "HeldOutPartitionVerdict" ADD COLUMN IF NOT EXISTS "sittingId" TEXT;
CREATE INDEX IF NOT EXISTS "HeldOutPartitionVerdict_sittingId_idx"
    ON "HeldOutPartitionVerdict"("sittingId");
ALTER TABLE "HeldOutPartitionOutcome" ADD COLUMN IF NOT EXISTS "seed" INTEGER;
