-- ADR-0166 stage 5: a sandbox run and its steps, practice of its own kind.
--
-- Two new tables and nothing else: no existing table, row or index is touched,
-- so the migration cannot fail on existing data. Nothing reads these tables but
-- the sandbox record; no gate, certification, tier or partition does.
--
-- Rollback: DROP TABLE "SandboxStep"; DROP TABLE "SandboxRun"; and delete this
-- migration's row from _prisma_migrations. Only sandbox rows are lost.
CREATE TABLE IF NOT EXISTS "SandboxRun" (
    "id" TEXT NOT NULL,
    "runRef" TEXT NOT NULL,
    "venture" TEXT NOT NULL,
    "forgeId" TEXT NOT NULL,
    "seed" INTEGER NOT NULL,
    "generatorVersion" TEXT NOT NULL,
    "worldName" TEXT NOT NULL,
    "worldDigest" TEXT NOT NULL,
    "tasksDigest" TEXT NOT NULL,
    "taskIds" JSONB NOT NULL,
    "startedBy" TEXT NOT NULL,
    "scheduleOwner" TEXT,
    "status" TEXT NOT NULL DEFAULT 'open',
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "endedAt" TIMESTAMP(3),
    "totals" JSONB,
    CONSTRAINT "SandboxRun_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "sandbox_run_status" CHECK ("status" IN ('open', 'closed'))
);
CREATE UNIQUE INDEX IF NOT EXISTS "SandboxRun_runRef_key" ON "SandboxRun"("runRef");

CREATE TABLE IF NOT EXISTS "SandboxStep" (
    "id" TEXT NOT NULL,
    "sandboxRunId" TEXT NOT NULL,
    "seq" INTEGER NOT NULL,
    "taskId" TEXT NOT NULL,
    "moduleId" TEXT NOT NULL,
    "step" TEXT NOT NULL,
    "at" TIMESTAMP(3) NOT NULL,
    "actor" TEXT NOT NULL,
    "agentId" TEXT,
    "sandboxIds" JSONB NOT NULL,
    "payload" JSONB NOT NULL,
    "verdict" TEXT,
    "reasons" JSONB,
    "forgeMatches" BOOLEAN,
    "recordedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "SandboxStep_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "SandboxStep_sandboxRunId_fkey" FOREIGN KEY ("sandboxRunId")
        REFERENCES "SandboxRun"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "sandbox_step_step" CHECK ("step" IN
        ('filed', 'claimed', 'turn_a', 'proposed', 'approved', 'forge_answer', 'turn_b')),
    CONSTRAINT "sandbox_step_verdict" CHECK ("verdict" IS NULL OR "verdict" IN
        ('PASS', 'FAIL', 'NOT_GRADED'))
);
CREATE UNIQUE INDEX IF NOT EXISTS "SandboxStep_run_seq_key" ON "SandboxStep"("sandboxRunId", "seq");
CREATE INDEX IF NOT EXISTS "SandboxStep_sandboxRunId_idx" ON "SandboxStep"("sandboxRunId");
