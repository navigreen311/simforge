-- ADR-0091 - a battery examines a run against the instruction set the run NAMES, never the newest.
--
-- The writer upserts on (forgeId, moduleId, contentHash). Three readers keyed on the first two,
-- and nothing made the writer's key real: no unique constraint, no index on contentHash.
--
-- `capital-forge/statement_ingest` was the live proof. Two rows - `sha256:statement_ingest_v1_2_0`
-- from 2026-08-21 and `sha256:adr47-live` from 2026-09-07 - and a battery there probed the FIRST
-- row's never-do list (an unordered scan, first non-empty wins) while reporting the SECOND row's
-- version and hash (`createdAt DESC`, first). Two rows in one exam, and neither answer said so.
--
-- This index is the half that outlives the code: a future writer that keys on two columns now
-- fails loudly instead of quietly adding a row that some reader will prefer.
CREATE UNIQUE INDEX "ForgeInstructionSet_forgeId_moduleId_contentHash_key"
    ON "ForgeInstructionSet" ("forgeId", "moduleId", "contentHash");

COMMENT ON INDEX "ForgeInstructionSet_forgeId_moduleId_contentHash_key" IS
    'The writer''s own key, enforced. A module may hold several instruction sets - a second hash is a second row by design - but never two rows for one hash. ADR-0091.';
