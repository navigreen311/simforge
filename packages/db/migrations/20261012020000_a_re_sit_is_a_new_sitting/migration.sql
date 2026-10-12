-- ADR-0160. Re-sits: a ref is an exam, each OperationRun row one sitting of it.
-- Every sitting is kept; none replaces another. Existing rows are sitting 1 and are not rewritten:
-- `sittingVerdict` stays NULL on them, and a reader takes their `verdict` as their own.

ALTER TABLE "OperationRun" ADD COLUMN IF NOT EXISTS "sitting" INTEGER NOT NULL DEFAULT 1;
ALTER TABLE "OperationRun" ADD COLUMN IF NOT EXISTS "sittingVerdict" TEXT;

DROP INDEX IF EXISTS "OperationRun_runRef_key";
CREATE UNIQUE INDEX IF NOT EXISTS "OperationRun_runRef_sitting_key"
    ON "OperationRun" ("runRef", "sitting");
CREATE INDEX IF NOT EXISTS "OperationRun_runRef_idx" ON "OperationRun" ("runRef");

ALTER TABLE "SubmittedProbeAnswer" ADD COLUMN IF NOT EXISTS "sitting" INTEGER NOT NULL DEFAULT 1;
