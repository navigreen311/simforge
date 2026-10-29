-- ADR-0163 (B96): one sealed partition per venture AND forge.
--
-- ADR-0113 ruling 2 held one per venture, so sealing one forge's partition
-- retired another forge's. A venture that operates two forges needs both
-- sealed at once.
--
-- The new index is built before the old one is dropped, so there is never a
-- moment with neither. Every row that satisfies the old index satisfies the
-- new one, so the build cannot fail on existing data. Nothing is rewritten:
-- a partition retired by another forge's seal stays retired.
CREATE UNIQUE INDEX IF NOT EXISTS "HeldOutPartition_one_sealed_per_venture_forge"
    ON "HeldOutPartition"("ventureId", "forgeId") WHERE "status" = 'sealed';

DROP INDEX IF EXISTS "HeldOutPartition_one_sealed_per_venture";
