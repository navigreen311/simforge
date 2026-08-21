-- Operation-cert incidents (content-hash VOID) are not tied to a scenario Run, so a SoftwareGap
-- must be allowed to exist without a runId. Relax the NOT NULL (the FK is kept for scenario gaps).
ALTER TABLE "SoftwareGap" ALTER COLUMN "runId" DROP NOT NULL;
