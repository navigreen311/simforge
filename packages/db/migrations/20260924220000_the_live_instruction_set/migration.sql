-- ADR-0125: the live instruction set is the one The Office last submitted,
-- and a partition records the instruction hashes it was authored from.
--
-- lastSubmittedAt is backfilled from what was recorded, not guessed: a
-- submission rewrites its (forge, module, hash) scenario rows, so their
-- newest createdAt is when The Office last named that set. A set with no
-- recorded submission keeps NULL and falls back to its own createdAt.
-- Idempotent.
ALTER TABLE "ForgeInstructionSet" ADD COLUMN IF NOT EXISTS "lastSubmittedAt" TIMESTAMP(3);

UPDATE "ForgeInstructionSet" f
   SET "lastSubmittedAt" = s.last
  FROM (
        SELECT "forgeId", "moduleId", "instructionContentHash", max("createdAt") AS last
          FROM "OperationScenarioSubmission"
         GROUP BY 1, 2, 3
       ) s
 WHERE f."lastSubmittedAt" IS NULL
   AND s."forgeId" = f."forgeId"
   AND s."moduleId" = f."moduleId"
   AND s."instructionContentHash" = f."contentHash";

-- Null on partitions authored before this: a hash nobody recorded is not
-- guessed, and such a partition is not graded.
ALTER TABLE "HeldOutPartition" ADD COLUMN IF NOT EXISTS "instructionHashes" JSONB;
