-- Sandbox-vs-production parity SLA (v1.1). Each row is a parity measurement for a forge capability;
-- a score below the SLA marks the forge `unsafe_to_certify`.
CREATE TABLE "ForgeParity" (
    "id"              TEXT NOT NULL,
    "forgeCap"        TEXT NOT NULL,
    "parityScore"    DOUBLE PRECISION NOT NULL,
    "slaThreshold"   DOUBLE PRECISION NOT NULL,
    "unsafeToCertify" BOOLEAN NOT NULL DEFAULT false,
    "sampleSize"      INTEGER NOT NULL DEFAULT 0,
    "method"          TEXT NOT NULL DEFAULT 'manual',
    "notes"           TEXT,
    "measuredAt"      TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "measuredBy"      TEXT NOT NULL DEFAULT 'system',
    "createdAt"       TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "ForgeParity_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "ForgeParity_forgeCap_idx" ON "ForgeParity"("forgeCap");
CREATE INDEX "ForgeParity_measuredAt_idx" ON "ForgeParity"("measuredAt");
