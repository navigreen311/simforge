-- ADR-0162: a held-out partition records who sits it - The Office's live grants on its
-- modules, stated at authoring - and the seal binds that roster.
--
-- HeldOutPartition.roster       - {"stated_at", "grants": [{"grant_id", "agent_id",
--                                 "module_id"}]}, in-scope grants only, sorted.
-- HeldOutPartition.rosterDigest - sha256 of the canonical roster; folded into
--                                 contentDigest at seal.
-- Both null on every existing partition: they keep the ADR-0152 roster and their digest.
-- Nothing backfilled. Idempotent.
ALTER TABLE "HeldOutPartition" ADD COLUMN IF NOT EXISTS "roster" JSONB;
ALTER TABLE "HeldOutPartition" ADD COLUMN IF NOT EXISTS "rosterDigest" TEXT;
