-- ADR-0113: a partition's sealer is never its author, and one venture
-- holds at most one sealed partition - by the database.
--
-- Idempotent. No partition had been sealed anywhere when this was written:
-- the ADR-0108 tables reach the dev DB in the same sitting.
ALTER TABLE "HeldOutPartition" ADD COLUMN IF NOT EXISTS "sealedBy" TEXT;

-- Ruling 1. Compared the way the service compares: trimmed, case-folded.
ALTER TABLE "HeldOutPartition"
    DROP CONSTRAINT IF EXISTS "held_out_partition_sealer_is_not_author";
ALTER TABLE "HeldOutPartition"
    ADD CONSTRAINT "held_out_partition_sealer_is_not_author"
    CHECK ("sealedBy" IS NULL OR lower(trim("sealedBy")) <> lower(trim("authoredBy")));

-- A partition that left `authoring` names who sealed it.
ALTER TABLE "HeldOutPartition"
    DROP CONSTRAINT IF EXISTS "held_out_partition_seal_names_sealer";
ALTER TABLE "HeldOutPartition"
    ADD CONSTRAINT "held_out_partition_seal_names_sealer"
    CHECK ("status" = 'authoring' OR "sealedBy" IS NOT NULL);

-- Ruling 2. Two seals racing could both seal. The second commit now fails.
CREATE UNIQUE INDEX IF NOT EXISTS "HeldOutPartition_one_sealed_per_venture"
    ON "HeldOutPartition"("ventureId") WHERE "status" = 'sealed';

-- The seal's own audit record. Append-only, one per seal.
CREATE TABLE IF NOT EXISTS "HeldOutPartitionSeal" (
    "id" TEXT NOT NULL,
    "partitionId" TEXT NOT NULL REFERENCES "HeldOutPartition"("id"),
    "ventureId" TEXT NOT NULL,
    "authoredBy" TEXT NOT NULL,
    "sealedBy" TEXT NOT NULL,
    "contentDigest" TEXT NOT NULL,
    "retiredPartitionIds" JSONB NOT NULL DEFAULT '[]',
    "sealedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "HeldOutPartitionSeal_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "held_out_partition_seal_two_people"
        CHECK (lower(trim("sealedBy")) <> lower(trim("authoredBy")))
);
CREATE UNIQUE INDEX IF NOT EXISTS "HeldOutPartitionSeal_partitionId_key"
    ON "HeldOutPartitionSeal"("partitionId");
CREATE INDEX IF NOT EXISTS "HeldOutPartitionSeal_ventureId_idx"
    ON "HeldOutPartitionSeal"("ventureId");
