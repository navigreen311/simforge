-- Scenario Bank (feat: scenario-bank batch 1). New library table + lifecycle/provenance.
-- Does NOT touch the runtime "Scenario" table -- existing scenario ids are preserved.
CREATE TABLE "BankScenario" (
    "id"                 TEXT NOT NULL,
    "publicId"           TEXT NOT NULL,
    "scenarioId"         TEXT,
    "title"              TEXT NOT NULL,
    "pack"               TEXT NOT NULL,
    "family"             TEXT NOT NULL,
    "tier"               TEXT NOT NULL,
    "situation"          TEXT NOT NULL DEFAULT '',
    "expectedBehaviors"  TEXT[] NOT NULL DEFAULT '{}',
    "adversarialTactics" TEXT[] NOT NULL DEFAULT '{}',
    "jurisdictionFlags"  TEXT[] NOT NULL DEFAULT '{}',
    "status"             TEXT NOT NULL DEFAULT 'draft',
    "aiDrafted"          BOOLEAN NOT NULL DEFAULT false,
    "sourceType"         TEXT NOT NULL DEFAULT 'manual',
    "sourceRef"          TEXT,
    "sourceExcerpt"      TEXT,
    "createdBy"          TEXT NOT NULL DEFAULT 'unknown',
    "reviewedBy"         TEXT,
    "reviewedAt"         TIMESTAMP(3),
    "version"            INTEGER NOT NULL DEFAULT 1,
    "supersedesId"       TEXT,
    "createdAt"          TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt"          TIMESTAMP(3) NOT NULL,
    CONSTRAINT "BankScenario_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "BankScenario_publicId_key" ON "BankScenario"("publicId");
CREATE UNIQUE INDEX "BankScenario_scenarioId_key" ON "BankScenario"("scenarioId");
CREATE INDEX "BankScenario_status_idx" ON "BankScenario"("status");
CREATE INDEX "BankScenario_pack_idx" ON "BankScenario"("pack");
CREATE INDEX "BankScenario_family_idx" ON "BankScenario"("family");
CREATE INDEX "BankScenario_tier_idx" ON "BankScenario"("tier");
CREATE INDEX "BankScenario_sourceType_idx" ON "BankScenario"("sourceType");

-- Backfill: every existing pack scenario becomes a committed / legacy bank entry, id preserved.
-- pack code (gs/ml/cg) maps to the venture name -- family + number derive from the scenario id.
-- The runtime "situation" (cold_open) lives in the pack YAML, not the DB, so it is referenced.
INSERT INTO "BankScenario" (
    "id", "publicId", "scenarioId", "title", "pack", "family", "tier",
    "situation", "expectedBehaviors", "status", "aiDrafted", "sourceType",
    "sourceRef", "createdBy", "version", "createdAt", "updatedAt"
)
SELECT
    'bank_' || s."scenarioId",
    'legacy_' || s."scenarioId",
    s."scenarioId",
    s."title",
    CASE split_part(s."scenarioId", '.', 2)
        WHEN 'gs' THEN 'greenstone'
        WHEN 'ml' THEN 'medlink'
        WHEN 'cg' THEN 'caregrid'
        ELSE split_part(s."scenarioId", '.', 2)
    END,
    split_part(s."scenarioId", '.', 3),
    s."tier",
    '(Legacy scenario -- the situation/cold-open is defined in the pack YAML.)',
    COALESCE(s."complianceChecks", ARRAY[]::text[]),
    'committed',
    false,
    'legacy',
    s."yamlPath",
    'legacy-backfill',
    1,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM "Scenario" s;
