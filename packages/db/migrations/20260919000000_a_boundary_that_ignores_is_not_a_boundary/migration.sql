-- ADR-0083 - a boundary that ignores is not a boundary.
--
-- Two fields both sides believed were delivered and neither stored. Pydantic's default is to
-- IGNORE an undeclared field, so a submitter could send `expected_answer` and `village_agent_ref`
-- and get a 200 back with nothing kept. The schemas now declare them and refuse extras; these are
-- the columns that make the acceptance true.

-- The transcribable half of an answer key (ADR-0069 ruling 2, ADR-0077, ADR-0082).
-- Nullable as a SET: a scenario with no `expected_answer` is stored and is not gradable by
-- transcription, which is the honest state of the 44 split keys until they are approved.
ALTER TABLE "OperationScenarioSubmission"
    ADD COLUMN "expectedAct"        TEXT,
    ADD COLUMN "expectedRecord"     TEXT,
    ADD COLUMN "recordSubject"      TEXT,
    ADD COLUMN "recordClaim"        TEXT,
    ADD COLUMN "recordClaimOptions" JSONB,
    ADD COLUMN "expectedCaveat"     TEXT;

-- The subject and the claim are two halves of one RECORD line and neither is readable alone.
ALTER TABLE "OperationScenarioSubmission"
    ADD CONSTRAINT "scenario_record_subject_and_claim_travel_together"
    CHECK (("recordSubject" IS NULL) = ("recordClaim" IS NULL));

-- WHO IS SITTING THE EXAM, in the Village's vocabulary.
--
-- `OperationRun.agentId` is consumed as a VILLAGE ref by `check_agent_identity`, and The Office
-- sends its `office_agent_id` there - so every run it opened in September refused on identity and
-- six rows were corrected by hand from `office_agent_identity.village_agent_ref`. This is that
-- column crossing the boundary instead of being reconstructed afterwards.
ALTER TABLE "OperationRun"
    ADD COLUMN "villageAgentRef" TEXT;

CREATE INDEX "OperationRun_villageAgentRef_idx" ON "OperationRun" ("villageAgentRef");

COMMENT ON COLUMN "OperationRun"."villageAgentRef" IS
    'The Village ref of the agent sitting this exam (victor_serath), as distinct from agentId, which holds The Office''s own uuid and is what its certifications are keyed on. The examiner looks up this one; the far side is answered with the other. ADR-0083.';
