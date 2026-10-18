-- B131 (Ivan Green, 17 October 2026). Each stored probe answer records the token counts Ollama
-- reported for its call and the context window it was asked under, so a prompt that stops
-- fitting shows as a number. Nullable: rows written before this are not rewritten.

ALTER TABLE "SubmittedProbeAnswer" ADD COLUMN IF NOT EXISTS "promptEvalCount" INTEGER;
ALTER TABLE "SubmittedProbeAnswer" ADD COLUMN IF NOT EXISTS "evalCount" INTEGER;
ALTER TABLE "SubmittedProbeAnswer" ADD COLUMN IF NOT EXISTS "numCtx" INTEGER;
