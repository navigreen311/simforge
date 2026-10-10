-- ADR-0154: author and seal authenticate as the named person.
--
-- PartitionOperator: an enrolled person and a scrypt hash of their
-- credential. One per name, compared trimmed and case-folded.
-- PartitionOperatorEvent: every enrolment, authoring and seal, refusals
-- included. Append-only.
-- HeldOutPartition gains the two operators' ids; they must differ.
-- Idempotent.
CREATE TABLE IF NOT EXISTS "PartitionOperator" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "credentialHash" TEXT NOT NULL,
    "witnessedBy" TEXT,
    "enrolledAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "PartitionOperator_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX IF NOT EXISTS "PartitionOperator_one_per_name"
    ON "PartitionOperator" (lower(trim("name")));

CREATE TABLE IF NOT EXISTS "PartitionOperatorEvent" (
    "id" TEXT NOT NULL,
    "act" TEXT NOT NULL,
    "claimedName" TEXT NOT NULL,
    "operatorId" TEXT,
    "witnessOperatorId" TEXT,
    "outcome" TEXT NOT NULL,
    "refusal" TEXT,
    "partitionId" TEXT,
    "ventureId" TEXT,
    "at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "PartitionOperatorEvent_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "partition_operator_event_act" CHECK ("act" IN ('enrol', 'author', 'seal')),
    CONSTRAINT "partition_operator_event_outcome" CHECK ("outcome" IN ('done', 'refused'))
);
CREATE INDEX IF NOT EXISTS "PartitionOperatorEvent_partitionId_idx"
    ON "PartitionOperatorEvent"("partitionId");

ALTER TABLE "HeldOutPartition" ADD COLUMN IF NOT EXISTS "authoredByOperatorId" TEXT;
ALTER TABLE "HeldOutPartition" ADD COLUMN IF NOT EXISTS "sealedByOperatorId" TEXT;
DO $$ BEGIN
    ALTER TABLE "HeldOutPartition" ADD CONSTRAINT "held_out_partition_two_operators"
        CHECK ("sealedByOperatorId" IS NULL OR "authoredByOperatorId" IS NULL
               OR "sealedByOperatorId" <> "authoredByOperatorId");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
