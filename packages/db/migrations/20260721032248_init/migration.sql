-- CreateTable
CREATE TABLE "Agent" (
    "id" TEXT NOT NULL,
    "villageAgentId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "role" TEXT NOT NULL,
    "departmentId" TEXT NOT NULL,
    "gardnerFlag" BOOLEAN NOT NULL DEFAULT false,
    "level10Enabled" BOOLEAN NOT NULL DEFAULT false,
    "currentAutonomyLevel" TEXT NOT NULL DEFAULT 'L1',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Agent_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Department" (
    "id" TEXT NOT NULL,
    "villageKey" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "totalAgents" INTEGER NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Department_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Pack" (
    "id" TEXT NOT NULL,
    "packId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "version" TEXT NOT NULL,
    "ownerVenture" TEXT NOT NULL,
    "ownerHuman" TEXT NOT NULL,
    "phiRequired" BOOLEAN NOT NULL DEFAULT false,
    "complianceFlags" TEXT[],
    "integratedRunsAllowed" BOOLEAN NOT NULL DEFAULT false,
    "executionModeDefault" TEXT NOT NULL DEFAULT 'sandbox',
    "narrativeModeDefault" TEXT NOT NULL DEFAULT 'protected',
    "rubricProfile" TEXT NOT NULL,
    "yamlPath" TEXT NOT NULL,
    "yamlHash" TEXT NOT NULL,
    "signedBy" TEXT,
    "signedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Pack_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Scenario" (
    "id" TEXT NOT NULL,
    "scenarioId" TEXT NOT NULL,
    "packId" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "tier" TEXT NOT NULL,
    "testedAgentVillageId" TEXT NOT NULL,
    "testedForgeCaps" TEXT[],
    "trainingDomains" TEXT[],
    "seed" INTEGER NOT NULL,
    "yamlPath" TEXT NOT NULL,
    "yamlHash" TEXT NOT NULL,
    "sloSeconds" INTEGER NOT NULL,
    "complianceChecks" TEXT[],
    "isGolden" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Scenario_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ReadinessGate" (
    "id" TEXT NOT NULL,
    "packId" TEXT NOT NULL,
    "tierThresholds" JSONB NOT NULL,
    "cognitiveAggregateMin" DOUBLE PRECISION NOT NULL DEFAULT 0.75,
    "blindModePct" DOUBLE PRECISION NOT NULL DEFAULT 0.25,
    "arcFragmentationAutoFail" BOOLEAN NOT NULL DEFAULT true,
    "complianceRequirePass" BOOLEAN NOT NULL DEFAULT true,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "ReadinessGate_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Run" (
    "id" TEXT NOT NULL,
    "runId" TEXT NOT NULL,
    "scenarioId" TEXT NOT NULL,
    "packId" TEXT NOT NULL,
    "agentId" TEXT NOT NULL,
    "executionMode" TEXT NOT NULL,
    "narrativeMode" TEXT NOT NULL,
    "blindMode" BOOLEAN NOT NULL DEFAULT false,
    "status" TEXT NOT NULL,
    "startedAt" TIMESTAMP(3) NOT NULL,
    "endedAt" TIMESTAMP(3),
    "outcome" TEXT,
    "latencyMs" INTEGER,
    "tokensUsed" INTEGER,
    "costUsd" DOUBLE PRECISION,
    "ccbPreId" TEXT,
    "ccbPostId" TEXT,
    "transcript" JSONB,
    "evidenceBundleRef" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Run_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "TraceEvent" (
    "id" TEXT NOT NULL,
    "runId" TEXT NOT NULL,
    "timestamp" TIMESTAMP(3) NOT NULL,
    "eventType" TEXT NOT NULL,
    "phase" TEXT NOT NULL,
    "turnNumber" INTEGER,
    "payload" JSONB NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "TraceEvent_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CCB" (
    "id" TEXT NOT NULL,
    "snapshotId" TEXT NOT NULL,
    "agentVillageId" TEXT NOT NULL,
    "phase" TEXT NOT NULL,
    "takenAt" TIMESTAMP(3) NOT NULL,
    "contentHash" TEXT NOT NULL,
    "game" JSONB NOT NULL,
    "mate" JSONB NOT NULL,
    "soul" JSONB NOT NULL,
    "breath" JSONB NOT NULL,
    "fot" JSONB NOT NULL,
    "hfm" JSONB NOT NULL,
    "arc" JSONB NOT NULL,
    "echo" JSONB NOT NULL,
    "drift" JSONB NOT NULL,
    "ame" JSONB NOT NULL,
    "villageSchemaFingerprint" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "CCB_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CognitiveSnapshot" (
    "id" TEXT NOT NULL,
    "agentId" TEXT NOT NULL,
    "date" TIMESTAMP(3) NOT NULL,
    "ccbSnapshotId" TEXT NOT NULL,
    "deltas" JSONB NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "CognitiveSnapshot_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Scorecard" (
    "id" TEXT NOT NULL,
    "runId" TEXT NOT NULL,
    "p1Correctness" DOUBLE PRECISION,
    "p2Compliance" BOOLEAN,
    "p3ProcessFidelity" DOUBLE PRECISION,
    "p4TimeToResolution" DOUBLE PRECISION,
    "p5Escalation" DOUBLE PRECISION,
    "p6DocQuality" DOUBLE PRECISION,
    "p7CustomerExperience" DOUBLE PRECISION,
    "p8CostDiscipline" DOUBLE PRECISION,
    "c1BreathCoherence" DOUBLE PRECISION,
    "c2SoulStability" DOUBLE PRECISION,
    "c3FotPressureManagement" DOUBLE PRECISION,
    "c4ArcNarrativeCoherence" TEXT,
    "c5EchoRegretLoad" DOUBLE PRECISION,
    "c6HfmDriveBalance" DOUBLE PRECISION,
    "c7AmeReputationTrajectory" DOUBLE PRECISION,
    "cognitiveAggregate" DOUBLE PRECISION,
    "readinessGatePassed" BOOLEAN NOT NULL DEFAULT false,
    "autoFailReason" TEXT,
    "turnAnnotations" JSONB NOT NULL,
    "remediationRecs" JSONB,
    "cohortComparison" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Scorecard_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SoftwareGap" (
    "id" TEXT NOT NULL,
    "ticketId" TEXT NOT NULL,
    "runId" TEXT NOT NULL,
    "forge" TEXT NOT NULL,
    "module" TEXT NOT NULL,
    "severity" TEXT NOT NULL,
    "summary" TEXT NOT NULL,
    "detail" TEXT NOT NULL,
    "proposedFix" TEXT,
    "linearUrl" TEXT,
    "linearId" TEXT,
    "status" TEXT NOT NULL DEFAULT 'open',
    "firstSeenRunId" TEXT NOT NULL,
    "lastSeenRunId" TEXT NOT NULL,
    "occurrenceCount" INTEGER NOT NULL DEFAULT 1,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "SoftwareGap_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "VillageOSGap" (
    "id" TEXT NOT NULL,
    "ticketId" TEXT NOT NULL,
    "runId" TEXT NOT NULL,
    "framework" TEXT NOT NULL,
    "severity" TEXT NOT NULL,
    "summary" TEXT NOT NULL,
    "detail" TEXT NOT NULL,
    "proposedFix" TEXT,
    "linearUrl" TEXT,
    "linearId" TEXT,
    "status" TEXT NOT NULL DEFAULT 'open',
    "occurrenceCount" INTEGER NOT NULL DEFAULT 1,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "VillageOSGap_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "AgentCert" (
    "id" TEXT NOT NULL,
    "agentId" TEXT NOT NULL,
    "forgeCap" TEXT NOT NULL,
    "tier" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "issuedAt" TIMESTAMP(3) NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "revokedAt" TIMESTAMP(3),
    "revocationReason" TEXT,
    "certSnapshotId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "AgentCert_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "DeptCert" (
    "id" TEXT NOT NULL,
    "departmentId" TEXT NOT NULL,
    "forgeContext" TEXT NOT NULL,
    "tier" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "issuedAt" TIMESTAMP(3) NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "revokedAt" TIMESTAMP(3),
    "revocationReason" TEXT,
    "certSnapshotId" TEXT NOT NULL,
    "prerequisiteAgentCertIds" TEXT[],
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "DeptCert_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CertLifecycleEvent" (
    "id" TEXT NOT NULL,
    "agentCertId" TEXT,
    "deptCertId" TEXT,
    "event" TEXT NOT NULL,
    "timestamp" TIMESTAMP(3) NOT NULL,
    "actor" TEXT NOT NULL,
    "reason" TEXT,
    "snapshotIdAtEvent" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "CertLifecycleEvent_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CertSnapshot" (
    "id" TEXT NOT NULL,
    "snapshotId" TEXT NOT NULL,
    "certType" TEXT NOT NULL,
    "subject" TEXT NOT NULL,
    "forgeCap" TEXT,
    "forgeContext" TEXT,
    "tier" TEXT NOT NULL,
    "issuedAt" TIMESTAMP(3) NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "pinnedVersions" JSONB NOT NULL,
    "evidenceBundleRef" TEXT NOT NULL,
    "signingKeyId" TEXT NOT NULL,
    "signature" TEXT NOT NULL,
    "contentHash" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "CertSnapshot_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "AutonomyEvent" (
    "id" TEXT NOT NULL,
    "agentId" TEXT NOT NULL,
    "fromLevel" TEXT NOT NULL,
    "toLevel" TEXT NOT NULL,
    "reason" TEXT NOT NULL,
    "triggeredBy" TEXT,
    "runIdContext" TEXT,
    "approvalId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AutonomyEvent_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ObjectRegistryEntry" (
    "id" TEXT NOT NULL,
    "urn" TEXT NOT NULL,
    "kind" TEXT NOT NULL,
    "canonicalId" TEXT NOT NULL,
    "metadata" JSONB NOT NULL,
    "tombstoned" BOOLEAN NOT NULL DEFAULT false,
    "tombstonedAt" TIMESTAMP(3),
    "tombstonedBy" TEXT,
    "tombstonedReason" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "ObjectRegistryEntry_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "LineageEdge" (
    "id" TEXT NOT NULL,
    "fromUrn" TEXT NOT NULL,
    "toUrn" TEXT NOT NULL,
    "relationType" TEXT NOT NULL,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "LineageEdge_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Constitution" (
    "id" TEXT NOT NULL,
    "version" TEXT NOT NULL,
    "ratifiedAt" TIMESTAMP(3) NOT NULL,
    "ratifiedBy" TEXT NOT NULL,
    "yamlContent" TEXT NOT NULL,
    "contentHash" TEXT NOT NULL,
    "supersededByVersion" TEXT,
    "supersededAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Constitution_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ConstitutionalAmendment" (
    "id" TEXT NOT NULL,
    "amendmentId" TEXT NOT NULL,
    "baseConstitutionId" TEXT NOT NULL,
    "proposedAt" TIMESTAMP(3) NOT NULL,
    "proposedBy" TEXT NOT NULL,
    "coolingPeriodEndsAt" TIMESTAMP(3) NOT NULL,
    "ratifiedAt" TIMESTAMP(3),
    "ratifiedBy" TEXT,
    "diffYaml" TEXT NOT NULL,
    "impactAnalysis" JSONB,
    "status" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "ConstitutionalAmendment_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "VillageFingerprint" (
    "id" TEXT NOT NULL,
    "fingerprint" TEXT NOT NULL,
    "capturedAt" TIMESTAMP(3) NOT NULL,
    "paths" JSONB NOT NULL,
    "isCurrent" BOOLEAN NOT NULL DEFAULT false,
    "flaggedByUser" BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT "VillageFingerprint_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "Agent_villageAgentId_key" ON "Agent"("villageAgentId");

-- CreateIndex
CREATE INDEX "Agent_villageAgentId_idx" ON "Agent"("villageAgentId");

-- CreateIndex
CREATE INDEX "Agent_departmentId_idx" ON "Agent"("departmentId");

-- CreateIndex
CREATE INDEX "Agent_currentAutonomyLevel_idx" ON "Agent"("currentAutonomyLevel");

-- CreateIndex
CREATE UNIQUE INDEX "Department_villageKey_key" ON "Department"("villageKey");

-- CreateIndex
CREATE UNIQUE INDEX "Pack_packId_key" ON "Pack"("packId");

-- CreateIndex
CREATE INDEX "Pack_ownerVenture_idx" ON "Pack"("ownerVenture");

-- CreateIndex
CREATE UNIQUE INDEX "Pack_packId_version_key" ON "Pack"("packId", "version");

-- CreateIndex
CREATE UNIQUE INDEX "Scenario_scenarioId_key" ON "Scenario"("scenarioId");

-- CreateIndex
CREATE INDEX "Scenario_packId_idx" ON "Scenario"("packId");

-- CreateIndex
CREATE INDEX "Scenario_testedAgentVillageId_idx" ON "Scenario"("testedAgentVillageId");

-- CreateIndex
CREATE INDEX "Scenario_tier_idx" ON "Scenario"("tier");

-- CreateIndex
CREATE INDEX "Scenario_isGolden_idx" ON "Scenario"("isGolden");

-- CreateIndex
CREATE UNIQUE INDEX "ReadinessGate_packId_key" ON "ReadinessGate"("packId");

-- CreateIndex
CREATE UNIQUE INDEX "Run_runId_key" ON "Run"("runId");

-- CreateIndex
CREATE INDEX "Run_scenarioId_idx" ON "Run"("scenarioId");

-- CreateIndex
CREATE INDEX "Run_agentId_idx" ON "Run"("agentId");

-- CreateIndex
CREATE INDEX "Run_status_idx" ON "Run"("status");

-- CreateIndex
CREATE INDEX "Run_startedAt_idx" ON "Run"("startedAt");

-- CreateIndex
CREATE INDEX "TraceEvent_runId_idx" ON "TraceEvent"("runId");

-- CreateIndex
CREATE INDEX "TraceEvent_timestamp_idx" ON "TraceEvent"("timestamp");

-- CreateIndex
CREATE UNIQUE INDEX "CCB_snapshotId_key" ON "CCB"("snapshotId");

-- CreateIndex
CREATE INDEX "CCB_agentVillageId_phase_idx" ON "CCB"("agentVillageId", "phase");

-- CreateIndex
CREATE INDEX "CCB_takenAt_idx" ON "CCB"("takenAt");

-- CreateIndex
CREATE INDEX "CognitiveSnapshot_agentId_idx" ON "CognitiveSnapshot"("agentId");

-- CreateIndex
CREATE UNIQUE INDEX "CognitiveSnapshot_agentId_date_key" ON "CognitiveSnapshot"("agentId", "date");

-- CreateIndex
CREATE UNIQUE INDEX "Scorecard_runId_key" ON "Scorecard"("runId");

-- CreateIndex
CREATE INDEX "Scorecard_readinessGatePassed_idx" ON "Scorecard"("readinessGatePassed");

-- CreateIndex
CREATE UNIQUE INDEX "SoftwareGap_ticketId_key" ON "SoftwareGap"("ticketId");

-- CreateIndex
CREATE INDEX "SoftwareGap_forge_severity_status_idx" ON "SoftwareGap"("forge", "severity", "status");

-- CreateIndex
CREATE INDEX "SoftwareGap_ticketId_idx" ON "SoftwareGap"("ticketId");

-- CreateIndex
CREATE UNIQUE INDEX "VillageOSGap_ticketId_key" ON "VillageOSGap"("ticketId");

-- CreateIndex
CREATE INDEX "VillageOSGap_framework_severity_status_idx" ON "VillageOSGap"("framework", "severity", "status");

-- CreateIndex
CREATE UNIQUE INDEX "AgentCert_certSnapshotId_key" ON "AgentCert"("certSnapshotId");

-- CreateIndex
CREATE INDEX "AgentCert_status_idx" ON "AgentCert"("status");

-- CreateIndex
CREATE INDEX "AgentCert_expiresAt_idx" ON "AgentCert"("expiresAt");

-- CreateIndex
CREATE UNIQUE INDEX "AgentCert_agentId_forgeCap_key" ON "AgentCert"("agentId", "forgeCap");

-- CreateIndex
CREATE UNIQUE INDEX "DeptCert_certSnapshotId_key" ON "DeptCert"("certSnapshotId");

-- CreateIndex
CREATE INDEX "DeptCert_status_idx" ON "DeptCert"("status");

-- CreateIndex
CREATE UNIQUE INDEX "DeptCert_departmentId_forgeContext_key" ON "DeptCert"("departmentId", "forgeContext");

-- CreateIndex
CREATE INDEX "CertLifecycleEvent_agentCertId_idx" ON "CertLifecycleEvent"("agentCertId");

-- CreateIndex
CREATE INDEX "CertLifecycleEvent_deptCertId_idx" ON "CertLifecycleEvent"("deptCertId");

-- CreateIndex
CREATE INDEX "CertLifecycleEvent_event_idx" ON "CertLifecycleEvent"("event");

-- CreateIndex
CREATE UNIQUE INDEX "CertSnapshot_snapshotId_key" ON "CertSnapshot"("snapshotId");

-- CreateIndex
CREATE INDEX "CertSnapshot_signingKeyId_idx" ON "CertSnapshot"("signingKeyId");

-- CreateIndex
CREATE INDEX "AutonomyEvent_agentId_idx" ON "AutonomyEvent"("agentId");

-- CreateIndex
CREATE INDEX "AutonomyEvent_createdAt_idx" ON "AutonomyEvent"("createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "ObjectRegistryEntry_urn_key" ON "ObjectRegistryEntry"("urn");

-- CreateIndex
CREATE INDEX "ObjectRegistryEntry_kind_idx" ON "ObjectRegistryEntry"("kind");

-- CreateIndex
CREATE INDEX "ObjectRegistryEntry_tombstoned_idx" ON "ObjectRegistryEntry"("tombstoned");

-- CreateIndex
CREATE INDEX "ObjectRegistryEntry_canonicalId_idx" ON "ObjectRegistryEntry"("canonicalId");

-- CreateIndex
CREATE INDEX "LineageEdge_fromUrn_idx" ON "LineageEdge"("fromUrn");

-- CreateIndex
CREATE INDEX "LineageEdge_toUrn_idx" ON "LineageEdge"("toUrn");

-- CreateIndex
CREATE INDEX "LineageEdge_relationType_idx" ON "LineageEdge"("relationType");

-- CreateIndex
CREATE INDEX "LineageEdge_fromUrn_toUrn_relationType_idx" ON "LineageEdge"("fromUrn", "toUrn", "relationType");

-- CreateIndex
CREATE UNIQUE INDEX "Constitution_version_key" ON "Constitution"("version");

-- CreateIndex
CREATE INDEX "Constitution_version_idx" ON "Constitution"("version");

-- CreateIndex
CREATE UNIQUE INDEX "ConstitutionalAmendment_amendmentId_key" ON "ConstitutionalAmendment"("amendmentId");

-- CreateIndex
CREATE INDEX "ConstitutionalAmendment_status_idx" ON "ConstitutionalAmendment"("status");

-- CreateIndex
CREATE UNIQUE INDEX "VillageFingerprint_fingerprint_key" ON "VillageFingerprint"("fingerprint");

-- CreateIndex
CREATE INDEX "VillageFingerprint_isCurrent_idx" ON "VillageFingerprint"("isCurrent");

-- AddForeignKey
ALTER TABLE "Agent" ADD CONSTRAINT "Agent_departmentId_fkey" FOREIGN KEY ("departmentId") REFERENCES "Department"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Scenario" ADD CONSTRAINT "Scenario_packId_fkey" FOREIGN KEY ("packId") REFERENCES "Pack"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ReadinessGate" ADD CONSTRAINT "ReadinessGate_packId_fkey" FOREIGN KEY ("packId") REFERENCES "Pack"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Run" ADD CONSTRAINT "Run_scenarioId_fkey" FOREIGN KEY ("scenarioId") REFERENCES "Scenario"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Run" ADD CONSTRAINT "Run_packId_fkey" FOREIGN KEY ("packId") REFERENCES "Pack"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Run" ADD CONSTRAINT "Run_agentId_fkey" FOREIGN KEY ("agentId") REFERENCES "Agent"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Run" ADD CONSTRAINT "Run_ccbPreId_fkey" FOREIGN KEY ("ccbPreId") REFERENCES "CCB"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Run" ADD CONSTRAINT "Run_ccbPostId_fkey" FOREIGN KEY ("ccbPostId") REFERENCES "CCB"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "TraceEvent" ADD CONSTRAINT "TraceEvent_runId_fkey" FOREIGN KEY ("runId") REFERENCES "Run"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CognitiveSnapshot" ADD CONSTRAINT "CognitiveSnapshot_agentId_fkey" FOREIGN KEY ("agentId") REFERENCES "Agent"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Scorecard" ADD CONSTRAINT "Scorecard_runId_fkey" FOREIGN KEY ("runId") REFERENCES "Run"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SoftwareGap" ADD CONSTRAINT "SoftwareGap_runId_fkey" FOREIGN KEY ("runId") REFERENCES "Run"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "VillageOSGap" ADD CONSTRAINT "VillageOSGap_runId_fkey" FOREIGN KEY ("runId") REFERENCES "Run"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AgentCert" ADD CONSTRAINT "AgentCert_agentId_fkey" FOREIGN KEY ("agentId") REFERENCES "Agent"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AgentCert" ADD CONSTRAINT "AgentCert_certSnapshotId_fkey" FOREIGN KEY ("certSnapshotId") REFERENCES "CertSnapshot"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "DeptCert" ADD CONSTRAINT "DeptCert_departmentId_fkey" FOREIGN KEY ("departmentId") REFERENCES "Department"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "DeptCert" ADD CONSTRAINT "DeptCert_certSnapshotId_fkey" FOREIGN KEY ("certSnapshotId") REFERENCES "CertSnapshot"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CertLifecycleEvent" ADD CONSTRAINT "CertLifecycleEvent_agentCertId_fkey" FOREIGN KEY ("agentCertId") REFERENCES "AgentCert"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CertLifecycleEvent" ADD CONSTRAINT "CertLifecycleEvent_deptCertId_fkey" FOREIGN KEY ("deptCertId") REFERENCES "DeptCert"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AutonomyEvent" ADD CONSTRAINT "AutonomyEvent_agentId_fkey" FOREIGN KEY ("agentId") REFERENCES "Agent"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ConstitutionalAmendment" ADD CONSTRAINT "ConstitutionalAmendment_baseConstitutionId_fkey" FOREIGN KEY ("baseConstitutionId") REFERENCES "Constitution"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
