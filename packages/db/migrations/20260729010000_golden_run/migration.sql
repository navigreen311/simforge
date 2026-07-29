-- Recorded runs of the golden regression suite (ADR-0033). Additive; history only — nothing here
-- changes the committed baseline, a score, or a certification.
CREATE TABLE "GoldenRun" (
    "id"          TEXT NOT NULL,
    "passed"      BOOLEAN NOT NULL,
    "total"       INTEGER NOT NULL DEFAULT 0,
    "matched"     INTEGER NOT NULL DEFAULT 0,
    "regressions" INTEGER NOT NULL DEFAULT 0,
    "results"     JSONB NOT NULL DEFAULT '[]',
    "ranBy"       TEXT NOT NULL DEFAULT 'operator',
    "createdAt"   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt"   TIMESTAMP(3) NOT NULL,
    CONSTRAINT "GoldenRun_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "GoldenRun_createdAt_idx" ON "GoldenRun"("createdAt");
