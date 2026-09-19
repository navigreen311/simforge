-- ADR-0093 - a score that describes only the held-out half must say so.
--
-- On 19 September four certifications read `score 1.0 / threshold 1.0` beside three competence
-- dimensions at FAIL. The number was TRUE: every held-out probe passed, three attempts, eleven
-- probes. What it measured was not what "scored 1.0 on the exam" means to anybody reading the row.
--
-- The collapse number learned this first (ADR-0070): 0.0 is a collapsed variance under v1 and a
-- clean sweep under v2, so an unlabelled number is not a weaker record, it is an unreadable one.
-- The same discipline, applied to the score.
--
--   held_out_pass_rate_v1           held-out probes passed / held-out probes put, worst attempt
--   merged_dimension_pass_rate_v2   dimensions PASSED / dimensions carrying a verdict, BOTH halves
--
-- v2 cannot read 1.0 beside a failing dimension, because that dimension is in its denominator.
ALTER TABLE "OperationCertification"
    ADD COLUMN "score" DOUBLE PRECISION,
    ADD COLUMN "scoreMeasure" TEXT;

-- The rows that already exist were all decided on the held-out pass rate, because no other rule
-- existed when they were written. Labelling them v1 is a statement of fact about what produced
-- them, not a migration of their value - the same one-time backfill ADR-0070 did, and for the same
-- reason it took no DEFAULT: this is an answer about rows that exist, never a standing answer for
-- rows not yet written.
UPDATE "OperationCertification"
   SET "scoreMeasure" = 'held_out_pass_rate_v1'
 WHERE "score" IS NOT NULL;

-- Stated as a CHECK rather than NOT NULL because a row may legitimately carry no score: a
-- department_context unit has no dimensions to rate, and a timed-out run got no answer. What may
-- never happen is a number whose meaning is unknown.
ALTER TABLE "OperationCertification"
    ADD CONSTRAINT "OperationCertification_score_is_labelled"
    CHECK ("score" IS NULL OR "scoreMeasure" IS NOT NULL);

COMMENT ON COLUMN "OperationCertification"."scoreMeasure" IS
    'WHICH RULE produced `score`: held_out_pass_rate_v1 (SimForge''s half alone) or merged_dimension_pass_rate_v2 (both halves, and what a battery reports today). Versioned, not migrated. ADR-0093.';
