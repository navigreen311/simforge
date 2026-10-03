-- ADR-0146: acceptable acts on The Office's keys, and a module's mutating flag.
--
-- OperationScenarioSubmission.acceptableActs - every act that passes the act check, the
--                                              expected one included. Null: just expectedAct.
-- ForgeInstructionSet.mutating              - as declared. Null is read as mutating.
-- Nothing backfilled. Idempotent.
ALTER TABLE "OperationScenarioSubmission" ADD COLUMN IF NOT EXISTS "acceptableActs" JSONB;
ALTER TABLE "ForgeInstructionSet" ADD COLUMN IF NOT EXISTS "mutating" BOOLEAN;
