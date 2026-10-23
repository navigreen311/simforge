-- ADR-0161: every Unit B outcome The Office posts through the bridge module
-- `department_outcome`, refusals included. Append-only. Idempotent.
--
-- The partial unique index holds the idempotency key: at most one RECORDED
-- row carries a key, so a retry is answered from the row the first call wrote
-- and never writes a second department certification.
CREATE TABLE IF NOT EXISTS "DepartmentOutcomePost" (
    "id" TEXT NOT NULL,
    "runRef" TEXT,
    "officeVenture" TEXT,
    "officeAgentId" TEXT,
    "officeTrace" TEXT,
    "forgeRequestId" TEXT NOT NULL,
    "idempotencyKey" TEXT,
    "payloadDigest" TEXT,
    "outcome" TEXT NOT NULL,
    "refusal" TEXT,
    "recorded" INTEGER NOT NULL DEFAULT 0,
    "at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "DepartmentOutcomePost_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "department_outcome_post_outcome"
        CHECK ("outcome" IN ('recorded', 'replayed', 'refused'))
);
CREATE INDEX IF NOT EXISTS "DepartmentOutcomePost_runRef_idx"
    ON "DepartmentOutcomePost"("runRef");
CREATE UNIQUE INDEX IF NOT EXISTS "DepartmentOutcomePost_recorded_key_idx"
    ON "DepartmentOutcomePost"("idempotencyKey") WHERE "outcome" = 'recorded';
