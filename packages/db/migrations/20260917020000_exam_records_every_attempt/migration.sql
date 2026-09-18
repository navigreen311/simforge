-- An exam records every attempt, not just its verdict.
--
-- Ivan's ruling, 17 September 2026: the exam runs at PRODUCTION settings - temperature and
-- token limit included - and a pass means passed every attempt. The battery sits the same
-- exam three times and any attempt failing is a fail.
--
-- WHY THAT MAKES A COLUMN NECESSARY
--
--   At production settings this Village runs its agents at temperature 0.7, so an attempt
--   is a SAMPLE. "Passed" and "passed once out of three" are different facts about an
--   agent and they produce the same verdict string. Without the attempts a reader cannot
--   tell a clean three-of-three from a lucky two-of-three, and on a FAIL cannot tell which
--   attempt failed or how.
--
-- WHY IT IS NOT ON `OperationRun` AND NOT ON THE GATE-RESULT BODY
--
--   The Office's response manifest states the rule: it is entitled to learn WHETHER an
--   agent passed and by how much against what threshold. How many times the agent sat the
--   exam, and what each attempt scored, is SimForge's record of its own examination. It is
--   read back through `battery_result_for` - the second read, which is SimForge's own and
--   is not manifest-governed - so no field is added to a contract to carry it.
--
--   The verdict The Office reads is already the weakest of the three, which is the whole of
--   what the ruling requires it to see.
--
-- SHAPE: a JSON array, one object per attempt, in the order they were sat:
--   [{attempt, seed, passed, score, probes_put, unreadable_answers, failure_modes}]
-- Verdicts, counts and named modes. No transcripts, no probes, no scenario content.
--
-- Additive only. No existing column is touched and no row is rewritten.
ALTER TABLE "OperationCertification" ADD COLUMN "examAttempts" JSONB;

COMMENT ON COLUMN "OperationCertification"."examAttempts" IS
  'Every attempt at this exam, in order: [{attempt, seed, passed, score, probes_put, unreadable_answers, failure_modes}]. A pass means passed every attempt (ADR-0062).';
