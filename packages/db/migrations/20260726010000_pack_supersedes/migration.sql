-- Pack authoring (Part B): record which pack version an edited pack replaces.
-- Additive + nullable. Existing packs are untouched (supersedesPackId stays NULL); no id changes.
ALTER TABLE "Pack" ADD COLUMN "supersedesPackId" TEXT;
