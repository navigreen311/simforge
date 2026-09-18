-- ADR-0072 - a withheld certification says why, and breadth is its own named rule.
--
-- Until now a `provisional` said nothing about which withhold produced it. Every reader
-- re-derived the hold from the raw numbers - the web card rebuilt `collapsed` from the spread and
-- the dimension count - which works right up to the moment a rule changes, and then every reader
-- is explaining an old hold under a rule that never applied to it. The same lesson as
-- `rubricSpreadMeasure` one migration ago.
--
-- Nullable, and the null is meaningful rather than missing: a CERTIFIED row has nothing to say
-- here, a FAILED row was not withheld, and a row written before this migration was held for a
-- reason nobody recorded. NOT backfilled for exactly that reason - inventing a reason for a
-- historical hold would be writing a basis the row never had, and this repository has now ruled
-- twice that a recorded result's basis is never rewritten.
ALTER TABLE "OperationCertification"
    ADD COLUMN "withheldBecause" JSONB;

COMMENT ON COLUMN "OperationCertification"."withheldBecause" IS
    'Why full certification was withheld (ADR-0072). A JSON list of named reasons: no_competence_dimension_carried_a_verdict, the_rubric_did_not_discriminate, a_declared_never_do_obligation_went_unexercised, the_competence_half_did_not_run, the_exam_was_not_sat_on_a_named_model_file. Written only on a provisional row; NULL on rows predating this column, which were held for a reason nobody recorded.';
