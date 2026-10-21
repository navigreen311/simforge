-- B135 (Ivan Green, 18 October 2026). Each stored probe answer records whether its call
-- started from a clean cache (the model unloaded first and loaded by the call) and Ollama's
-- load_duration in milliseconds. Nullable: rows written before this are not rewritten.

ALTER TABLE "SubmittedProbeAnswer" ADD COLUMN IF NOT EXISTS "coldStart" BOOLEAN;
ALTER TABLE "SubmittedProbeAnswer" ADD COLUMN IF NOT EXISTS "loadMs" INTEGER;
