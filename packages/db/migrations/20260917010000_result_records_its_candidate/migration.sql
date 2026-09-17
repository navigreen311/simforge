-- A result records its candidate, not just the candidate's name.
--
-- `agentModel` holds `ollama/llama3.1:8b`. That is a REQUEST with a label on it. The
-- same tag re-pulled at a different quantization is a different model file; the same
-- weights served at temperature 0.0 or 0.7 are a different exam. Both produce that
-- identical string, and a certification earned under one reads as current under the
-- other.
--
-- Ivan's ruling, 17 September 2026: a certification counts only if it was earned on the
-- exact model the agent runs in production - model name, model file including its size
-- and quantization, and the generation settings - and SimForge records all of it on
-- every result. A change to any of the three means re-certification.
--
-- WHY JSON AND NOT SIX COLUMNS
--
--   The same argument `operationRubricResults` settled: the shape is a named record that
--   will gain fields as providers gain facts worth recording, and six columns would make
--   the seventh a migration. What is NOT negotiable is the `fingerprint` inside it - a
--   hash over every field, so a re-certification check is a string comparison rather than
--   a field-by-field argument nobody will write the same way twice.
--
-- WHY IT IS ON BOTH TABLES
--
--   `OperationCertification` is the record, and it carries the candidate for EVERY
--   result - a failed run's candidate is what makes the failure reproducible, and a
--   provisional hold's is often the reason it was held.
--
--   `OperationRun` is what The Office reads (`GET /operation/gate-result/{run_ref}`),
--   and it carries it for the reason `agentModel` is on the run rather than joined from
--   the certification: that join is a lookup on a natural key, not an identity.
--
-- WHY NULLABLE
--
--   The same three row shapes that legitimately name no model: a run still open, a run
--   stamped TIMEOUT, and a Unit-B run cleared by department state. The requirement lives
--   where the verdict class is known - the gate-result path refuses to certify an outcome
--   whose identity is absent or incomplete, and holds one with no model FILE at
--   `provisional`, because a cloud provider is for practice runs.
--
-- Additive only. No existing column is touched and no row is rewritten.
ALTER TABLE "OperationRun" ADD COLUMN "agentModelIdentity" JSONB;
ALTER TABLE "OperationCertification" ADD COLUMN "agentModelIdentity" JSONB;

COMMENT ON COLUMN "OperationRun"."agentModelIdentity" IS
  'The candidate in full: model name, model file digest and size, quantization, generation settings, and a fingerprint over all of it. NULL wherever agentModel is NULL.';

COMMENT ON COLUMN "OperationCertification"."agentModelIdentity" IS
  'The candidate in full, recorded on every result. A change to the model, its file or its settings means re-certification (ADR-0060).';
