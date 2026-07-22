-- Locale layer (ADR-0041): a pack declares the language of its rubric-judge prompts. Default 'en'.
ALTER TABLE "Pack" ADD COLUMN "locale" TEXT NOT NULL DEFAULT 'en';
