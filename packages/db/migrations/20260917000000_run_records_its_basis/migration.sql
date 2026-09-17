-- A run records the basis of its own verdict.
--
-- `OperationRun` already had `score`, `threshold` and `certifiedTier`. All three were
-- written by nothing: `close_run` accepted them as keyword arguments and the only caller
-- - the gate-result handler - passed the states and nothing else. So every closed run
-- carried a verdict and no basis, `gate_result_for` omitted all three keys, and The
-- Office's `record_result` refused the resulting `certified` row for want of a tier.
--
-- The three columns needed no migration. This one adds the fourth fact that did.
--
-- WHY `agentModel` IS ON THE RUN AND NOT ONLY ON THE CERTIFICATION
--
--   Migration 20260910000000 put `agentModel` on `OperationCertification`, which is the
--   right place for a certification's candidate. But The Office reads a RUN's verdict
--   (`GET /operation/gate-result/{run_ref}`), and `certified_records_its_basis` demands
--   the model on every answered verdict. Reconstructing it from the certification would
--   mean joining on `(forgeId, moduleId, agentId)` bounded by time - a lookup, not an
--   identity, as `battery_result_for` states at length - and a field The Office refuses a
--   row without must not arrive by inference.
--
-- WHY NULLABLE, WHICH IS NOT THE SAME AS OPTIONAL
--
--   Three row shapes legitimately have no model: a run still inside its window, a run
--   stamped TIMEOUT (nothing answered), and a Unit-B run cleared by department state.
--   The requirement lives where the verdict class is known - the gate-result path refuses
--   an `agent_operation` outcome resolving to `certified` that names no model - not in a
--   NOT NULL that would be wrong for all three.
--
-- Additive only. No existing column is touched and no row is rewritten.
ALTER TABLE "OperationRun" ADD COLUMN "agentModel" TEXT;

COMMENT ON COLUMN "OperationRun"."agentModel" IS
  'provider/model that answered this run''s battery, e.g. ollama/llama3.1:8b. NULL where nothing answered: still open, timed out, or a Unit-B run cleared by department state.';
