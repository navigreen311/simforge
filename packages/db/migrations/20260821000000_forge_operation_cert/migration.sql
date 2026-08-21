-- Forge Operation Certification (Rev 2, agent × forge × module). ADDITIVE ONLY — no destructive
-- ops; the existing 8-dimension DOMAIN rubric and its certs (AgentCert/DeptCert/CertSnapshot) are
-- untouched. No backfill.

-- The curriculum an operation cert BINDS to: an instruction set for a forge module, authored by
-- The Office; SimForge tests an agent against it. A cert records the instruction/api version and
-- content_hash it was earned under (change → re-cert; content_hash mismatch at run → VOID).
CREATE TABLE "ForgeInstructionSet" (
    "id"                 TEXT NOT NULL,
    "forgeId"            TEXT NOT NULL,
    "moduleId"           TEXT NOT NULL,
    "instructionVersion" TEXT NOT NULL,
    "forgeApiVersion"    TEXT NOT NULL,
    "authoredBy"         TEXT NOT NULL,
    "authoredAt"         TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "contentHash"        TEXT NOT NULL,
    "createdAt"          TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "ForgeInstructionSet_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "ForgeInstructionSet_forgeId_idx"  ON "ForgeInstructionSet"("forgeId");
CREATE INDEX "ForgeInstructionSet_moduleId_idx" ON "ForgeInstructionSet"("moduleId");

-- An operation certification at agent × forge × module granularity. One table, two unit types
-- (agent_operation / department_context). operationRubricVersion is SEPARATE from and independent
-- of the domain rubric_version (required). `state` is the distinct 7-state machine —
-- never_certified/failed/stale are never a low score. operationRubricResults is a NAMED LIST. The
-- DENOMINATOR (functionsCertified of functionsInModule) travels on every Unit A result.
CREATE TABLE "OperationCertification" (
    "id"                     TEXT NOT NULL,
    -- Common
    "unitType"               TEXT NOT NULL,  -- agent_operation | department_context
    "state"                  TEXT NOT NULL,  -- 7-state machine (distinct states)
    "forgeId"                TEXT NOT NULL,
    "instructionVersion"     TEXT NOT NULL,
    "forgeApiVersion"        TEXT NOT NULL,
    "instructionContentHash" TEXT NOT NULL,
    "operationRubricVersion" TEXT NOT NULL,  -- SEPARATE from domain rubric_version, required
    -- Unit A (agent operation)
    "agentId"                TEXT,
    "moduleId"               TEXT,
    "functionsCertified"     INTEGER,
    "functionsInModule"      INTEGER,        -- DENOMINATOR
    "maxCertifiedTrustTier"  TEXT,           -- auto_execute | propose | suggest
    "perScenarioClass"       JSONB,
    "operationRubricResults" JSONB,          -- NAMED LIST: [{dimension, verdict, score?, threshold?}]
    "rubricDimensionSpread"  DOUBLE PRECISION,
    "failureModesObserved"   JSONB,
    "versionSensitivity"     JSONB,          -- {module: [major|minor|patch]} (Rev 2 Q4)
    "expiresAt"              TIMESTAMP(3),
    -- Unit B (department context)
    "departmentId"               TEXT,
    "forgeContext"               TEXT,
    "ventureContext"             TEXT,
    "escalationPathVerified"     BOOLEAN,
    "complianceCouplingVerified" BOOLEAN,
    -- Common lifecycle
    "createdAt"  TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "reviewedBy" TEXT,
    "reviewedAt" TIMESTAMP(3),
    CONSTRAINT "OperationCertification_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "OperationCertification_unitType_idx"     ON "OperationCertification"("unitType");
CREATE INDEX "OperationCertification_state_idx"        ON "OperationCertification"("state");
CREATE INDEX "OperationCertification_forgeId_idx"      ON "OperationCertification"("forgeId");
CREATE INDEX "OperationCertification_agentId_idx"      ON "OperationCertification"("agentId");
CREATE INDEX "OperationCertification_moduleId_idx"     ON "OperationCertification"("moduleId");
CREATE INDEX "OperationCertification_departmentId_idx" ON "OperationCertification"("departmentId");
