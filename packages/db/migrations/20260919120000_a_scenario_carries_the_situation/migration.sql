-- ADR-0087 - a submitted scenario carries the situation the agent is asked.
--
-- Without it SimForge holds an answer key and has nothing to put: P2's grader was built complete
-- and its input did not exist. The Office holds the situation in `summary` and does not send it -
-- its own generator says "there is no `situation` field on either side of the [wire]".
--
-- SimForge declares first, which is the ordering its own `extra="forbid"` imposes: a field the
-- receiver has not declared is now REFUSED rather than dropped, so the sender cannot go first.
--
-- NULLABLE, deliberately. The Office does not send it yet and a NOT NULL would refuse every
-- curriculum it currently submits, stopping a venture that is already certifying. A scenario
-- without one is stored, cannot be put, and grades NOT_RUN by its own named reason.
ALTER TABLE "OperationScenarioSubmission"
    ADD COLUMN "situation" TEXT;

COMMENT ON COLUMN "OperationScenarioSubmission"."situation" IS
    'What the agent is ASKED. Distinct from expectedBehavior, which is what a good answer looks like - rendering that into a probe would hand the agent the answer. ADR-0087.';
