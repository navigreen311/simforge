-- Spec documents uploaded into a venture (Part B). Additive; provenance for the enrichment proposal
-- and the AI-drafted scenarios a spec produced. Nothing here is live until a human applies/commits.
CREATE TABLE "SpecDocument" (
    "id"                  TEXT NOT NULL,
    "ventureSlug"         TEXT NOT NULL,
    "filename"            TEXT NOT NULL,
    "extractedText"       TEXT NOT NULL DEFAULT '',
    "enrichmentProposal"  JSONB,
    "producedScenarioIds" TEXT[] NOT NULL DEFAULT '{}',
    "uploadedBy"          TEXT NOT NULL DEFAULT 'unknown',
    "createdAt"           TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt"           TIMESTAMP(3) NOT NULL,
    CONSTRAINT "SpecDocument_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "SpecDocument_ventureSlug_idx" ON "SpecDocument"("ventureSlug");
ALTER TABLE "SpecDocument"
    ADD CONSTRAINT "SpecDocument_ventureSlug_fkey"
    FOREIGN KEY ("ventureSlug") REFERENCES "Venture"("slug") ON DELETE RESTRICT ON UPDATE CASCADE;
