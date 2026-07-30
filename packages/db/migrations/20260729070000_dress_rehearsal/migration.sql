-- Dress Rehearsal protocol (§15): gated go-live run with entry/exit criteria + signed sign-offs.
CREATE TABLE "DressRehearsal" (
    "id"           TEXT NOT NULL,
    "packId"       TEXT NOT NULL,
    "status"       TEXT NOT NULL DEFAULT 'open',
    "entryResults" JSONB NOT NULL DEFAULT '{}',
    "exitResults"  JSONB NOT NULL DEFAULT '{}',
    "signoffs"     JSONB NOT NULL DEFAULT '[]',
    "createdAt"    TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt"    TIMESTAMP(3) NOT NULL,
    CONSTRAINT "DressRehearsal_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "DressRehearsal_packId_idx" ON "DressRehearsal"("packId");
