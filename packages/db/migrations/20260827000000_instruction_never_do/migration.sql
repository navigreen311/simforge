-- Persist the module never-do list on the instruction set (Rev-2 audit FIX 2). Additive; default
-- empty. An empty list = the module has no never-do rules (never_do_adherence genuinely n/a); a
-- non-empty list = the never_do_violation dimension must be tested (untested = a coverage hole).
ALTER TABLE "ForgeInstructionSet" ADD COLUMN "neverDo" JSONB NOT NULL DEFAULT '[]';
