-- ADR-0092 ruling 4 - a certification records the scenario-set hash it was graded against.
--
-- `instructionContentHash` says which INSTRUCTIONS the run executed against. It says nothing about
-- which answer keys graded it. The binding was inference: `submitted_keys_for` selects by
-- (forge, module, instruction hash), so the key set was implied by a hash of the instructions and
-- written down nowhere. A key edited, or a key added, changes the exam while that hash stays put,
-- and every row goes on looking identical.
--
-- On 19 September four agents were examined against 31 approved keys and the only evidence of that
-- is this reconstruction. The column exists so the next one does not need reconstructing.
--
-- NULLABLE, and the null carries meaning: no submitted key was put, so the exam was graded against
-- no answer key. A digest of the empty set would claim it was graded against one. Rows written
-- before this column are null for a third reason - nobody recorded it - which is the same value
-- and a different fact, so the two are told apart by `createdAt`, not by this column.
ALTER TABLE "OperationCertification"
    ADD COLUMN "scenarioSetHash" TEXT;

COMMENT ON COLUMN "OperationCertification"."scenarioSetHash" IS
    'Which ANSWER KEYS this exam was graded against - a digest over the submitted scenarios actually put, in authored order, covering every field the grader compares. Distinct from instructionContentHash, which names the instructions. NULL = no submitted key was put. ADR-0092.';
