-- Temporal Realism Engine (v1.1). A reusable definition of time-based scenario dynamics: scheduled
-- events (delayed/async) and time-bombs (a deadline turn + a defuse action + a consequence).
CREATE TABLE "TemporalScenario" (
    "id"          TEXT NOT NULL,
    "name"        TEXT NOT NULL,
    "scenarioId"  TEXT,
    "events"      JSONB NOT NULL DEFAULT '[]',
    "timeBombs"   JSONB NOT NULL DEFAULT '[]',
    "createdAt"   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt"   TIMESTAMP(3) NOT NULL,
    CONSTRAINT "TemporalScenario_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "TemporalScenario_scenarioId_idx" ON "TemporalScenario"("scenarioId");
