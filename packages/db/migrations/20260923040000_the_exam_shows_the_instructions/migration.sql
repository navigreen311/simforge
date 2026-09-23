-- ADR-0107: an agent is examined on the instructions it was shown, and the exam records the gap.
--
-- `ForgeInstructionSet` stored only `neverDo`. The submitted keys are written against four
-- sections -- correct_sequence, failure_signatures, inputs, retry_vs_escalate -- whose prose was
-- never stored and never shown, so every exam graded an agent on instructions nobody sent it.
--
-- NULL on both columns for existing rows, and that is the honest value: no curriculum has sent
-- section prose yet, and no certification recorded the gap because nothing measured it.
ALTER TABLE "ForgeInstructionSet" ADD COLUMN IF NOT EXISTS "sections" JSONB;
ALTER TABLE "OperationCertification" ADD COLUMN IF NOT EXISTS "instructionSections" JSONB;
