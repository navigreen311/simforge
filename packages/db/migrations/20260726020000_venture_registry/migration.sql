-- Venture Registry: the single source of truth for the "venture" field.
-- Additive. Seeds the 6 known Green Companies ventures, normalizes the Scenario-Bank pack tag, and
-- adds a FK from Pack.ownerVenture. Existing packs/scenarios keep their ids; nothing is destroyed.

CREATE TABLE "Venture" (
    "id"                     TEXT NOT NULL,
    "slug"                   TEXT NOT NULL,
    "name"                   TEXT NOT NULL,
    "description"            TEXT NOT NULL DEFAULT '',
    "status"                 TEXT NOT NULL DEFAULT 'in_development',
    "scenarioCode"           TEXT NOT NULL,
    "defaultComplianceFlags" TEXT[] NOT NULL DEFAULT '{}',
    "internalForges"         TEXT[] NOT NULL DEFAULT '{}',
    "capabilities"           TEXT[] NOT NULL DEFAULT '{}',
    "createdBy"              TEXT NOT NULL DEFAULT 'system',
    "createdAt"              TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt"              TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Venture_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "Venture_slug_key" ON "Venture"("slug");
CREATE INDEX "Venture_status_idx" ON "Venture"("status");

-- Seed the registry. The three ventures that already have packs are active with their real flags;
-- the other known ventures start empty (no fabricated capabilities) and in_development.
INSERT INTO "Venture"
    ("id","slug","name","description","status","scenarioCode",
     "defaultComplianceFlags","internalForges","capabilities","createdBy","createdAt","updatedAt")
VALUES
    ('vnt_medlink','medlink-pro','MedLink Pro','Healthcare staffing venture (PHI-adjacent).',
     'active','ml','{hipaa,hcqc_nv,oig_sam,i9}','{medlink-pro,vaf}','{}','seed',
     CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
    ('vnt_greenstone','greenstone','Greenstone','Real-estate wholesaling venture.',
     'active','gs','{tcpa,state_wholesaling}','{funnelforge}','{}','seed',
     CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
    ('vnt_caregrid','caregrid','CareGrid','California home-health staffing (PHI).',
     'active','cg','{hipaa,cdph_ca,ccpa,oig_sam,i9}','{caregrid}','{}','seed',
     CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
    ('vnt_argus','argus','Argus','','in_development','ar','{}','{}','{}','seed',
     CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
    ('vnt_collingswood','collingswood','Collingswood & Co.','','in_development','cw','{}','{}','{}',
     'seed',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
    ('vnt_burkham','burkham-wickmont','Burkham Wickmont','','in_development','bw','{}','{}','{}',
     'seed',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP);

-- Normalize the Scenario-Bank venture tag to the canonical registry slug (only 'medlink' differs;
-- 'greenstone'/'caregrid' already match). Scenario ids, content, and status are untouched.
UPDATE "BankScenario" SET "pack" = 'medlink-pro' WHERE "pack" = 'medlink';

-- Now every Pack.ownerVenture references a seeded Venture.slug -- add the foreign key.
ALTER TABLE "Pack"
    ADD CONSTRAINT "Pack_ownerVenture_fkey"
    FOREIGN KEY ("ownerVenture") REFERENCES "Venture"("slug") ON DELETE RESTRICT ON UPDATE CASCADE;
