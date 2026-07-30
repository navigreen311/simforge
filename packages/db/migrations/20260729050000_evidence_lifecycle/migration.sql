-- Evidence lifecycle (§12.3): retention, tiers, legal hold, redaction class, Merkle chain-of-custody.
CREATE TABLE "EvidenceRecord" (
    "id"             TEXT NOT NULL,
    "bundleId"       TEXT NOT NULL,
    "ref"            TEXT NOT NULL,
    "contentHash"    TEXT NOT NULL,
    "prevAnchor"     TEXT,
    "chainAnchor"    TEXT NOT NULL,
    "redactionClass" TEXT NOT NULL DEFAULT 'standard',
    "tier"           TEXT NOT NULL DEFAULT 'hot',
    "retentionUntil" TIMESTAMP(3) NOT NULL,
    "legalHold"      BOOLEAN NOT NULL DEFAULT false,
    "packId"         TEXT,
    "createdAt"      TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "purgedAt"       TIMESTAMP(3),
    CONSTRAINT "EvidenceRecord_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "EvidenceRecord_bundleId_key" ON "EvidenceRecord"("bundleId");
CREATE INDEX "EvidenceRecord_createdAt_idx" ON "EvidenceRecord"("createdAt");

CREATE TABLE "EvidenceAccess" (
    "id"       TEXT NOT NULL,
    "recordId" TEXT NOT NULL,
    "accessor" TEXT NOT NULL,
    "reason"   TEXT NOT NULL DEFAULT '',
    "at"       TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "EvidenceAccess_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "EvidenceAccess_recordId_idx" ON "EvidenceAccess"("recordId");
