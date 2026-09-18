-- ADR-0070 - the collapse measure is versioned, not migrated.
--
-- `rubricDimensionSpread` has been produced by two different rules: a population variance
-- (compared against 0.02) and, from this migration, a range (compared against 0.10, with a
-- ceiling band and a count of independently-sourced scenario classes). The column holds both,
-- and this one names which.
--
-- Ivan's ruling: a recorded result's basis is never rewritten. So NO existing number is
-- recomputed here. The backfill below writes a LABEL, not a value, and the label is true of
-- every row it touches: each was computed with the variance rule, because until now there was
-- no other.
ALTER TABLE "OperationCertification"
    ADD COLUMN "rubricSpreadMeasure" TEXT;

-- The one-time statement of fact. Only rows that CARRY a number get a label, because a label on
-- an absent number would be a claim about a measurement that was never taken - a Unit B row has
-- no rubric dimensions to compare.
UPDATE "OperationCertification"
   SET "rubricSpreadMeasure" = 'population_variance_v1'
 WHERE "rubricDimensionSpread" IS NOT NULL;

-- NOT NULL was the wrong shape: it would force a label onto the rows that have nothing to label.
-- The real invariant is that the number and its rule travel TOGETHER. An unlabelled number is not
-- a weaker record, it is an unreadable one: 0.0 is a collapsed variance under v1 and a clean sweep
-- under v2.
ALTER TABLE "OperationCertification"
    ADD CONSTRAINT "operation_cert_spread_has_a_measure"
    CHECK ("rubricDimensionSpread" IS NULL OR "rubricSpreadMeasure" IS NOT NULL);

COMMENT ON COLUMN "OperationCertification"."rubricSpreadMeasure" IS
    'Which rule produced rubricDimensionSpread: population_variance_v1 (variance < 0.02) or dimension_range_v2 (range < 0.10, floor below the 0.95 ceiling band, >= 2 scenario classes exercised). ADR-0070. Never rewritten.';

COMMENT ON COLUMN "OperationCertification"."rubricDimensionSpread" IS
    'The collapse number. Its MEANING depends on rubricSpreadMeasure - a variance under v1, a range under v2. Read the two together or not at all.';
