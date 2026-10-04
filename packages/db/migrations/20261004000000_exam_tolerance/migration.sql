-- ADR-0147: a Unit A exam tolerates one slip, and says why it failed.
--
-- OperationCertification.toleratedSlips  - slips forgiven on the exam (0 or 1). Null on rows
--                                          graded before the rule.
-- OperationCertification.scenarioReasons - every non-PASS probe of every attempt with its
--                                          reasons tuple. Codes only.
-- Nothing backfilled. Idempotent.
ALTER TABLE "OperationCertification" ADD COLUMN IF NOT EXISTS "toleratedSlips" INTEGER;
ALTER TABLE "OperationCertification" ADD COLUMN IF NOT EXISTS "scenarioReasons" JSONB;
ALTER TABLE "OperationCertification"
    DROP CONSTRAINT IF EXISTS "operation_cert_tolerated_slips";
ALTER TABLE "OperationCertification"
    ADD CONSTRAINT "operation_cert_tolerated_slips"
    CHECK ("toleratedSlips" IS NULL OR "toleratedSlips" IN (0, 1));
