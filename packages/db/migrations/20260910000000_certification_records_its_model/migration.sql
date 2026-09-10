-- A certification names the model that answered it.
--
-- `OperationCertification` records the version matrix a cert was earned under -
-- `instructionVersion`, `forgeApiVersion`, `instructionContentHash`,
-- `operationRubricVersion` - so a later reader can recompute staleness when any of them
-- move. Every one of those describes the EXAM. None of them describes the CANDIDATE.
--
-- An agent certified against `llama3.1:8b` produces a row saying the agent passed. Swap
-- the model and the row still reads as current, because nothing in it ever named what
-- answered the probe. The Office's `certification` table had the same gap and its
-- migration 0035 closes it there; this is the same fact on this side of the boundary.
--
-- WHY THE COLUMN IS NULLABLE, WHICH IS NOT THE SAME AS OPTIONAL
--
--   Nullable because rows exist that legitimately have no model: a battery that timed
--   out never got an answer, and a `department_context` unit is cleared by department
--   state rather than by a model sitting an exam. Forcing those to carry a value would
--   make them name a candidate that never answered - the same error as letting a real
--   verdict omit one, in the opposite direction.
--
--   The requirement lives where the fact is known: the gate-result path refuses to
--   persist an `agent_operation` outcome that does not name its model. A CHECK here
--   cannot see the verdict class, and a NOT NULL would be a rule that is wrong for two
--   legitimate row shapes.
--
-- Additive only. No existing column is touched and no row is rewritten.
ALTER TABLE "OperationCertification" ADD COLUMN "agentModel" TEXT;

COMMENT ON COLUMN "OperationCertification"."agentModel" IS
  'provider/model that answered the battery, e.g. ollama/llama3.1:8b. NULL where nothing answered: a timed-out run, or a department_context unit cleared by department state.';
