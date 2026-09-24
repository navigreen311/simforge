-- ADR-0114: a partition verdict keeps why, on SimForge's side only.
--
-- One row per probe behind a verdict: module, class, outcome, failure-mode
-- codes, and how the answer arrived. Never scenario content, never the
-- answer. No route reads this table. Append-only. Idempotent.
CREATE TABLE IF NOT EXISTS "HeldOutPartitionOutcome" (
    "id" TEXT NOT NULL,
    "verdictId" TEXT NOT NULL REFERENCES "HeldOutPartitionVerdict"("id"),
    "partitionId" TEXT NOT NULL REFERENCES "HeldOutPartition"("id"),
    "agentId" TEXT NOT NULL,
    "scenarioId" TEXT NOT NULL REFERENCES "HeldOutPartitionScenario"("id"),
    "moduleId" TEXT NOT NULL,
    "scenarioClass" TEXT NOT NULL,
    "outcome" TEXT NOT NULL,
    "failureModes" JSONB NOT NULL DEFAULT '[]',
    "answerState" TEXT NOT NULL,
    "tokensOutput" INTEGER,
    "latencyMs" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "HeldOutPartitionOutcome_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "held_out_partition_outcome_value"
        CHECK ("outcome" IN ('PASS', 'FAIL', 'NOT_RUN')),
    CONSTRAINT "held_out_partition_outcome_answer_state"
        CHECK ("answerState" IN ('answered', 'empty', 'unparseable', 'provider_error'))
);
CREATE INDEX IF NOT EXISTS "HeldOutPartitionOutcome_verdictId_idx"
    ON "HeldOutPartitionOutcome"("verdictId");
CREATE INDEX IF NOT EXISTS "HeldOutPartitionOutcome_partitionId_idx"
    ON "HeldOutPartitionOutcome"("partitionId");
CREATE INDEX IF NOT EXISTS "HeldOutPartitionOutcome_agentId_idx"
    ON "HeldOutPartitionOutcome"("agentId");
