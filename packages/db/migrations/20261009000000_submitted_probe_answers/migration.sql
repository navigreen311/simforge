-- ADR-0153: the agent's answers to The Office's own probes, and who read them.
--
-- SubmittedProbeAnswer: one row per submitted probe per exam attempt, the
-- answer verbatim. Never a held-out answer: the CHECK refuses the held-out
-- classes and the partition's go-ahead class at the database.
--
-- SubmittedAnswerRead: one row per read by The Office, refusals included.
-- Append-only. Idempotent.
CREATE TABLE IF NOT EXISTS "SubmittedProbeAnswer" (
    "id" TEXT NOT NULL,
    "runRef" TEXT NOT NULL,
    "forgeId" TEXT NOT NULL,
    "moduleId" TEXT NOT NULL,
    "instructionContentHash" TEXT NOT NULL,
    "scenarioRef" TEXT NOT NULL,
    "scenarioClass" TEXT NOT NULL,
    "ordinal" INTEGER NOT NULL,
    "attempt" INTEGER NOT NULL,
    "seed" INTEGER NOT NULL,
    "verdict" TEXT NOT NULL,
    "reasons" JSONB NOT NULL DEFAULT '[]',
    "answerText" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "SubmittedProbeAnswer_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "submitted_probe_answer_never_held_out"
        CHECK ("scenarioClass" NOT IN ('never_do_violation', 'silent_failure', 'permitted_request')),
    CONSTRAINT "submitted_probe_answer_verdict"
        CHECK ("verdict" IN ('PASS', 'FAIL', 'NOT_RUN'))
);
CREATE INDEX IF NOT EXISTS "SubmittedProbeAnswer_runRef_idx"
    ON "SubmittedProbeAnswer"("runRef");

CREATE TABLE IF NOT EXISTS "SubmittedAnswerRead" (
    "id" TEXT NOT NULL,
    "runRef" TEXT NOT NULL,
    "officeVenture" TEXT,
    "officeAgentId" TEXT,
    "officeTrace" TEXT,
    "forgeRequestId" TEXT NOT NULL,
    "outcome" TEXT NOT NULL,
    "refusal" TEXT,
    "answersReturned" INTEGER NOT NULL DEFAULT 0,
    "at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "SubmittedAnswerRead_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "submitted_answer_read_outcome"
        CHECK ("outcome" IN ('returned', 'refused'))
);
CREATE INDEX IF NOT EXISTS "SubmittedAnswerRead_runRef_idx"
    ON "SubmittedAnswerRead"("runRef");
