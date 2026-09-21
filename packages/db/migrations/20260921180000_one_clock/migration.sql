-- ADR-0101 - timestamps are stored one way across the service.
--
-- 108 timestamp columns in this schema are `timestamp without time zone` and hold naive UTC.
-- `models/base.py:_now` says so in its own comment: "Naive UTC - matches Prisma `timestamp`
-- columns; avoids asyncpg local-time shift."
--
-- Three of ours were `timestamp with time zone`, from one hand-written migration
-- (20260918000000_the_answer_key_is_kept:51, `TIMESTAMPTZ NOT NULL DEFAULT now()`), and the
-- mismatch is silent in the worst way. The ORM writes a NAIVE UTC datetime; Postgres interprets a
-- naive literal against a timestamptz column in the SESSION TimeZone, which on this host is
-- `America/Los_Angeles`; so 04:50 UTC was stored as 04:50 PDT = 11:50 UTC. Seven hours late, no
-- error, and correct-looking to any reader who prints the column in UTC.
--
-- **It made forensics lie.** Those 44 rows were reported as a curriculum "rewritten six hours
-- after the sweep". They were written thirty minutes BEFORE it, in the same Gate 8 pass that
-- opened the runs the sweep graded - which `xmin`, the 41ms sub-second gap and the identical
-- scenario-set hashes all say, and the timestamp alone denied.
--
-- THE CONVERSION IS THE EXACT INVERSE OF THE DAMAGE.
--
-- The damage was: take a naive value, read it as America/Los_Angeles. The inverse is: render the
-- stored instant in America/Los_Angeles and keep the wall clock. `AT TIME ZONE 'UTC'` would NOT
-- do this - it would preserve the seven-hour error and call it corrected.
--
-- This is right for every row PROVIDED every row was written by that path with the session zone at
-- America/Los_Angeles. Every row in `OperationScenarioSubmission` was: 44 rows, one instant, one
-- writer. `TrainingProposal` has zero rows, so its two columns convert with nothing to repair.
-- A row written from a session in another zone would be corrected by the wrong offset, and there
-- is no way to tell such a row apart afterwards - which is the second reason the mismatch had to
-- go rather than be documented.
ALTER TABLE "OperationScenarioSubmission"
    ALTER COLUMN "createdAt" TYPE TIMESTAMP
    USING ("createdAt" AT TIME ZONE 'America/Los_Angeles');

ALTER TABLE "OperationScenarioSubmission"
    ALTER COLUMN "createdAt" SET DEFAULT (now() AT TIME ZONE 'UTC');

ALTER TABLE "TrainingProposal"
    ALTER COLUMN "createdAt" TYPE TIMESTAMP
    USING ("createdAt" AT TIME ZONE 'America/Los_Angeles');

ALTER TABLE "TrainingProposal"
    ALTER COLUMN "reviewedAt" TYPE TIMESTAMP
    USING ("reviewedAt" AT TIME ZONE 'America/Los_Angeles');

COMMENT ON COLUMN "OperationScenarioSubmission"."createdAt" IS
    'Naive UTC, like every other timestamp in this schema. It was TIMESTAMPTZ until ADR-0101, and a naive UTC write into it was reinterpreted in the session zone and stored seven hours late without erroring.';
