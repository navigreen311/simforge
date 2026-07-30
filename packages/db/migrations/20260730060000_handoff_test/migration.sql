-- Multi-agent handoff integrity testing (v1.1). A department-level test of a cross-agent process:
-- an ordered chain of handoffs, checked for completeness, continuity, and consent preservation.
CREATE TABLE "HandoffTest" (
    "id"         TEXT NOT NULL,
    "name"       TEXT NOT NULL,
    "scenarioId" TEXT,
    "chain"      JSONB NOT NULL DEFAULT '[]',
    "createdAt"  TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt"  TIMESTAMP(3) NOT NULL,
    CONSTRAINT "HandoffTest_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "HandoffTest_scenarioId_idx" ON "HandoffTest"("scenarioId");
