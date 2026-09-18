-- The answer key The Office sends is kept.
--
-- `submit_curriculum` validated `operation_scenarios` and stored NOTHING. It upserted the
-- ForgeInstructionSet - version, content hash, never-do list - and returned. The scenarios,
-- each carrying an expected_behavior and an expected_escalation that somebody wrote and
-- Ivan Green approved, were discarded on arrival.
--
-- WHY THAT WAS A CEILING AND NOT ONLY A LOSS
--
--   Nothing could re-read what a venture said its agent should do. Nothing could RUN the
--   seven submittable classes. So only `never_do_adherence` and `failure_recognition` -
--   the two classes SimForge authors itself - ever carried a score, both at exactly 1.0
--   on a clean run, and `is_spread_collapsed` fires on two equal scores.
--
--   **No run could reach `certified`.** Not "usually did not": could not. The first of
--   three packages that close that (ADR-0069).
--
-- WHAT IS NOT HERE
--
--   No column for an expected ACT/RECORD shape. ADR-0069 rules that The Office states one
--   beside each expected behaviour so a submitted scenario is graded by transcription
--   rather than by a model reading another model's prose - but that field is not on the
--   payload yet. A column written by nothing is the defect this repository has recorded
--   seven times, and it is not being added an eighth. It arrives with the contract change.
--
--   No table for `module_not_applicable` either. The declared absences are echoed back to
--   The Office and still stored nowhere, so "this class cannot exist here" still cannot be
--   told from "nobody sent one" after the request ends. Named rather than fixed: the
--   ruling said one table.
--
-- THE KEY
--
--   (forgeId, moduleId, instructionContentHash) - the same natural key the instruction set
--   upserts on. A curriculum is a SET submitted whole, so the write deletes and re-inserts
--   for that key: a re-post of the same curriculum must not double it, and a re-post of a
--   changed one must not leave the old scenarios standing beside the new. A different
--   content hash is a different instruction set and gets its own rows.
--
-- Additive only. No existing table or column is touched.
CREATE TABLE "OperationScenarioSubmission" (
    "id"                     TEXT PRIMARY KEY,
    "forgeId"                TEXT NOT NULL,
    "moduleId"               TEXT NOT NULL,
    "instructionContentHash" TEXT NOT NULL,
    "scenarioClass"          TEXT NOT NULL,
    "instructionSection"     TEXT NOT NULL,
    "expectedBehavior"       TEXT NOT NULL,
    "expectedEscalation"     TEXT NOT NULL,
    "neverDoEntry"           TEXT,
    "ordinal"                INTEGER NOT NULL DEFAULT 0,
    "createdAt"              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX "OperationScenarioSubmission_forgeId_idx"    ON "OperationScenarioSubmission" ("forgeId");
CREATE INDEX "OperationScenarioSubmission_moduleId_idx"   ON "OperationScenarioSubmission" ("moduleId");
CREATE INDEX "OperationScenarioSubmission_hash_idx"       ON "OperationScenarioSubmission" ("instructionContentHash");
CREATE INDEX "OperationScenarioSubmission_class_idx"      ON "OperationScenarioSubmission" ("scenarioClass");

COMMENT ON TABLE "OperationScenarioSubmission" IS
  'The seven submittable scenario classes as The Office sent them, with the expected behaviour and escalation it authored. Not the held-out set: SimForge authors never_do_violation and silent_failure and keeps them unseen (ADR-0050).';

COMMENT ON COLUMN "OperationScenarioSubmission"."neverDoEntry" IS
  'Set only on a never_do_violation scenario, which a submitter may not send (ADR-0048). Should always be NULL; a row carrying one means the validator let something through.';
