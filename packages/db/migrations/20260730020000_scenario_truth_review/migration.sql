-- Scenario Truth Review Gate (v1.1). A per-scenario attestation that the scenario faithfully
-- represents reality before it may certify agents. Approved only when every checklist item holds.
CREATE TABLE "ScenarioTruthReview" (
    "id"          TEXT NOT NULL,
    "scenarioId"  TEXT NOT NULL,
    "status"      TEXT NOT NULL DEFAULT 'pending',
    "checklist"   JSONB NOT NULL DEFAULT '{}',
    "reviewer"    TEXT,
    "notes"       TEXT,
    "reviewedAt"  TIMESTAMP(3),
    "createdAt"   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt"   TIMESTAMP(3) NOT NULL,
    CONSTRAINT "ScenarioTruthReview_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "ScenarioTruthReview_scenarioId_key" ON "ScenarioTruthReview"("scenarioId");
