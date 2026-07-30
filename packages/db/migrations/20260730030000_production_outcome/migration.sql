-- Production Outcome Correlation (v1.1). Records real production performance per agent × forge
-- capability, so certification scores can be correlated against production reality.
CREATE TABLE "ProductionOutcome" (
    "id"              TEXT NOT NULL,
    "agentVillageId" TEXT NOT NULL,
    "forgeCap"        TEXT NOT NULL,
    "outcomeScore"   DOUBLE PRECISION NOT NULL,
    "period"          TEXT NOT NULL DEFAULT '',
    "sampleSize"      INTEGER NOT NULL DEFAULT 0,
    "source"          TEXT NOT NULL DEFAULT 'manual',
    "notes"           TEXT,
    "recordedAt"      TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "recordedBy"      TEXT NOT NULL DEFAULT 'system',
    CONSTRAINT "ProductionOutcome_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "ProductionOutcome_agentVillageId_idx" ON "ProductionOutcome"("agentVillageId");
CREATE INDEX "ProductionOutcome_forgeCap_idx" ON "ProductionOutcome"("forgeCap");
