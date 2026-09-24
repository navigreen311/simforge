-- ADR-0116 ruling 2: citation is graded separately from the decision.
--
-- A decision that passed can still carry a discipline finding - an
-- escalation that did not name the prohibition. Kept apart from
-- `failureModes`, so a finding never fails a decision. Idempotent.
ALTER TABLE "HeldOutPartitionOutcome"
    ADD COLUMN IF NOT EXISTS "findings" JSONB NOT NULL DEFAULT '[]';
