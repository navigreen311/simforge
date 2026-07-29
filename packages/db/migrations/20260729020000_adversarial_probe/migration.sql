-- Recorded red-team probe runs (ADR-0028). Additive; ADVISORY history only — a probe result never
-- blocks, revokes, or changes a certification.
CREATE TABLE "AdversarialProbe" (
    "id"             TEXT NOT NULL,
    "scenarioId"     TEXT NOT NULL,
    "scenarioTitle"  TEXT NOT NULL DEFAULT '',
    "agent"          TEXT NOT NULL,
    "provider"       TEXT NOT NULL DEFAULT 'stub',
    "verdict"        TEXT NOT NULL,
    "probesRun"      INTEGER NOT NULL DEFAULT 0,
    "resisted"       INTEGER NOT NULL DEFAULT 0,
    "capitulated"    INTEGER NOT NULL DEFAULT 0,
    "resistanceRate" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "results"        JSONB NOT NULL DEFAULT '[]',
    "ranBy"          TEXT NOT NULL DEFAULT 'operator',
    "createdAt"      TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt"      TIMESTAMP(3) NOT NULL,
    CONSTRAINT "AdversarialProbe_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "AdversarialProbe_createdAt_idx" ON "AdversarialProbe"("createdAt");
