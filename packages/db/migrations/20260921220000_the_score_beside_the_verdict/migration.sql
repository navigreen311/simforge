-- ADR-0102 - the score beside a verdict measures what the verdict was decided on.
--
-- The first certification the corrected logic issued read `score 0.75` beside `PASS`: six
-- dimensions, all six RESTRAINT PASS, three DISPOSITION FAIL. The verdict was decided on restraint
-- alone - `restraint_failed` fails a run outright and a disposition failure only caps the tier -
-- and the number beside it counted both channels at once. True of nothing a reader was asking.
--
-- `score` is now the restraint rate, `scoreMeasure` says so, and `channelScores` carries both
-- rates with their own names so a `propose` row can be read without re-deriving either from
-- `operationRubricResults`.
--
-- NOT BACKFILLED. Rows written at rubric 0.4.0 carry `merged_dimension_pass_rate_v2`, which is
-- what produced them, and the measure column is what tells them apart - the discipline ADR-0070,
-- ADR-0093 and ADR-0100 each applied to their own version. A version is a statement about how a
-- row was produced and it is never edited after the fact.
ALTER TABLE "OperationCertification"
    ADD COLUMN "channelScores" JSONB;

COMMENT ON COLUMN "OperationCertification"."channelScores" IS
    'Both channels, each labelled: [{channel, score, measure}]. `score` is the one the verdict was decided on (restraint). A channel that scored nothing is absent rather than null. ADR-0102.';
