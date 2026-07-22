-- Cognitive-drift daily canary signals (ADR-0034).
-- Add the flat cognitive-signal vector, its baseline deltas, and the drift magnitude to
-- CognitiveSnapshot; give the JSON columns an empty-object default.
ALTER TABLE "CognitiveSnapshot" ADD COLUMN "values" JSONB NOT NULL DEFAULT '{}';
ALTER TABLE "CognitiveSnapshot" ADD COLUMN "driftMagnitude" DOUBLE PRECISION NOT NULL DEFAULT 0;
ALTER TABLE "CognitiveSnapshot" ALTER COLUMN "deltas" SET DEFAULT '{}';
