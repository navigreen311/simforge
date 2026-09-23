-- ADR-0108: Gate 9.5's held-out adversarial partition.
--
-- Venture-scoped, stored, sealed. SimForge authors it and The Office never reads it.
-- Append-only. The verdict carries no reason column: whether, never why.
CREATE TABLE IF NOT EXISTS "HeldOutPartition" (
    "id" TEXT NOT NULL,
    "ventureId" TEXT NOT NULL,
    "forgeId" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'authoring',
    "authoredBy" TEXT NOT NULL,
    "contentDigest" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "sealedAt" TIMESTAMP(3),
    CONSTRAINT "HeldOutPartition_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "held_out_partition_status"
        CHECK ("status" IN ('authoring', 'sealed', 'retired'))
);
CREATE INDEX IF NOT EXISTS "HeldOutPartition_ventureId_idx" ON "HeldOutPartition"("ventureId");
CREATE INDEX IF NOT EXISTS "HeldOutPartition_forgeId_idx" ON "HeldOutPartition"("forgeId");
CREATE INDEX IF NOT EXISTS "HeldOutPartition_status_idx" ON "HeldOutPartition"("status");

CREATE TABLE IF NOT EXISTS "HeldOutPartitionScenario" (
    "id" TEXT NOT NULL,
    "partitionId" TEXT NOT NULL REFERENCES "HeldOutPartition"("id"),
    "moduleId" TEXT NOT NULL,
    "scenarioClass" TEXT NOT NULL,
    "body" JSONB NOT NULL,
    "digest" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "HeldOutPartitionScenario_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "held_out_partition_scenario_class"
        CHECK ("scenarioClass" IN ('never_do_violation', 'silent_failure'))
);
CREATE INDEX IF NOT EXISTS "HeldOutPartitionScenario_partitionId_idx"
    ON "HeldOutPartitionScenario"("partitionId");
CREATE INDEX IF NOT EXISTS "HeldOutPartitionScenario_moduleId_idx"
    ON "HeldOutPartitionScenario"("moduleId");
CREATE INDEX IF NOT EXISTS "HeldOutPartitionScenario_digest_idx"
    ON "HeldOutPartitionScenario"("digest");

CREATE TABLE IF NOT EXISTS "HeldOutPartitionVerdict" (
    "id" TEXT NOT NULL,
    "partitionId" TEXT NOT NULL REFERENCES "HeldOutPartition"("id"),
    "ventureId" TEXT NOT NULL,
    "agentId" TEXT NOT NULL,
    "verdict" TEXT NOT NULL,
    "partitionDigest" TEXT NOT NULL,
    "instructionContentHash" TEXT,
    "decidedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "HeldOutPartitionVerdict_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "held_out_partition_verdict_value"
        CHECK ("verdict" IN ('PASS', 'FAIL', 'NOT_RUN', 'IN_PROGRESS', 'TIMEOUT'))
);
CREATE INDEX IF NOT EXISTS "HeldOutPartitionVerdict_partitionId_idx"
    ON "HeldOutPartitionVerdict"("partitionId");
CREATE INDEX IF NOT EXISTS "HeldOutPartitionVerdict_ventureId_idx"
    ON "HeldOutPartitionVerdict"("ventureId");
CREATE INDEX IF NOT EXISTS "HeldOutPartitionVerdict_agentId_idx"
    ON "HeldOutPartitionVerdict"("agentId");
