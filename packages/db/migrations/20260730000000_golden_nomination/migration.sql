-- Golden Benchmark Bank governance (§12.5): a scenario is promoted to the immutable gold set only
-- via formal nomination + multi-party council review (an ApprovalRequest) + a recorded freeze.
CREATE TABLE "GoldenNomination" (
    "id"                  TEXT NOT NULL,
    "scenarioId"          TEXT NOT NULL,
    "nominatedBy"         TEXT NOT NULL,
    "rationale"           TEXT NOT NULL DEFAULT '',
    "interRaterReliability" DOUBLE PRECISION,
    "approvalRequestId"   TEXT,
    "status"              TEXT NOT NULL DEFAULT 'pending',
    "frozenAt"            TIMESTAMP(3),
    "frozenBy"            TEXT,
    "createdAt"           TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt"           TIMESTAMP(3) NOT NULL,
    CONSTRAINT "GoldenNomination_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "GoldenNomination_scenarioId_idx" ON "GoldenNomination"("scenarioId");
CREATE INDEX "GoldenNomination_status_idx" ON "GoldenNomination"("status");
