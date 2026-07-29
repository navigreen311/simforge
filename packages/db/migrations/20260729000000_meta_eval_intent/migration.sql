-- Owner's advisory remediation intent per rubric dimension (Meta-Eval triage). Additive; ADVISORY
-- ONLY — nothing here changes a score, weight, or certification. One row per dimension.
CREATE TABLE "MetaEvalIntent" (
    "id"        TEXT NOT NULL,
    "dim"       TEXT NOT NULL,
    "intent"    TEXT NOT NULL,
    "note"      TEXT NOT NULL DEFAULT '',
    "updatedBy" TEXT NOT NULL DEFAULT 'owner',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "MetaEvalIntent_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "MetaEvalIntent_dim_key" ON "MetaEvalIntent"("dim");
