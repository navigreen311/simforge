-- Persisted, fleet-wide, scoped emergency safe mode (§11.7) — replaces the in-process singleton.
CREATE TABLE "SafeModeState" (
    "id"            TEXT NOT NULL,
    "scopeType"     TEXT NOT NULL,
    "scopeValue"    TEXT NOT NULL DEFAULT '',
    "active"        BOOLEAN NOT NULL DEFAULT true,
    "reason"        TEXT NOT NULL DEFAULT '',
    "activatedBy"   TEXT NOT NULL DEFAULT 'admin',
    "activatedAt"   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deactivatedAt" TIMESTAMP(3),
    "deactivatedBy" TEXT,
    "autoTriggered" BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT "SafeModeState_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "SafeModeState_active_idx" ON "SafeModeState"("active");
