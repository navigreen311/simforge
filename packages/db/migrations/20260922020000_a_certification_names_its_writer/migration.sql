-- ADR-0104 ruling 1: a certification records the process that wrote it.
--
-- The six certifications of 19 September 2026 name no process, no commit and no host. When the
-- question came -- which process wrote them -- nothing on the row could answer it, and the
-- attribution closed unattributed.
--
-- NULL for every existing row, and deliberately so. A backfill would have to guess, and a guessed
-- writer is worse than a blank one: it reads as a record.
ALTER TABLE "OperationCertification" ADD COLUMN IF NOT EXISTS "writtenBy" JSONB;
