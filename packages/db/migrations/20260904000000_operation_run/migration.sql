-- An operation battery IN FLIGHT.
--
-- Before this table SimForge held no record of a run between curriculum hand-over and
-- gate-result, so a battery that hung produced nothing at all: no row, no verdict, no
-- error, and the certification the unit already held stayed in place. The Office's
-- VERDICT_TO_STATE[TIMEOUT] -> in_training was correct and unreachable, because nothing
-- observed the run. An open row (endedAt IS NULL) past its window is that observation.
--
-- Additive only. No existing table or column is touched.
CREATE TABLE "OperationRun" (
    "id"                     TEXT NOT NULL,
    -- Correlates to the Office submission. UNIQUE because the Office reads a verdict BY
    -- this ref; two rows sharing one ref make the answer ambiguous.
    "runRef"                 TEXT NOT NULL,
    "unit"                   TEXT NOT NULL,
    "forgeId"                TEXT NOT NULL,
    "moduleId"               TEXT,
    "agentId"                TEXT,
    "departmentId"           TEXT,
    "instructionContentHash" TEXT NOT NULL,
    "rubricKind"             TEXT NOT NULL,
    "rubricVersion"          TEXT NOT NULL,
    "startedAt"              TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- NULL = still open. This column, and only this column, is what "did not finish" means.
    "endedAt"                TIMESTAMP(3),
    -- Per-run, so a run is judged against the window it STARTED under.
    "windowMinutes"          INTEGER NOT NULL DEFAULT 180,
    "verdict"                TEXT,
    -- Distinct from endedAt: endedAt means a result was produced, and a timed-out run
    -- never produced one.
    "timedOutAt"             TIMESTAMP(3),
    -- A timed-out run carries NO score. Zero would be a claim about the agent.
    "score"                  DOUBLE PRECISION,
    "threshold"              DOUBLE PRECISION,
    "certifiedTier"          TEXT,
    "scenarioCount"          INTEGER NOT NULL DEFAULT 0,
    "coverageDenominator"    INTEGER NOT NULL DEFAULT 0,
    "createdAt"              TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "OperationRun_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "OperationRun_runRef_key" ON "OperationRun"("runRef");
CREATE INDEX "OperationRun_unit_idx" ON "OperationRun"("unit");
CREATE INDEX "OperationRun_forgeId_idx" ON "OperationRun"("forgeId");
CREATE INDEX "OperationRun_moduleId_idx" ON "OperationRun"("moduleId");
CREATE INDEX "OperationRun_agentId_idx" ON "OperationRun"("agentId");
CREATE INDEX "OperationRun_departmentId_idx" ON "OperationRun"("departmentId");
-- The sweep's query is exactly (endedAt IS NULL AND startedAt < cutoff).
CREATE INDEX "OperationRun_endedAt_idx" ON "OperationRun"("endedAt");
CREATE INDEX "OperationRun_verdict_idx" ON "OperationRun"("verdict");
