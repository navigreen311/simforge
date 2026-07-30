-- Approval Workflow Engine (§11.5): governed decisions + append-only signed decision journal.
CREATE TABLE "ApprovalRequest" (
    "id"                TEXT NOT NULL,
    "kind"              TEXT NOT NULL,
    "subject"           JSONB NOT NULL DEFAULT '{}',
    "summary"           TEXT NOT NULL DEFAULT '',
    "quorumRule"        TEXT NOT NULL DEFAULT 'single',
    "requiredApprovers" TEXT[] NOT NULL DEFAULT '{}',
    "status"            TEXT NOT NULL DEFAULT 'pending',
    "createdBy"         TEXT NOT NULL DEFAULT 'system',
    "createdAt"         TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expiresAt"         TIMESTAMP(3),
    "resolvedAt"        TIMESTAMP(3),
    "resolution"        TEXT,
    CONSTRAINT "ApprovalRequest_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "ApprovalRequest_status_idx" ON "ApprovalRequest"("status");
CREATE INDEX "ApprovalRequest_kind_idx" ON "ApprovalRequest"("kind");

CREATE TABLE "ApprovalDecision" (
    "id"        TEXT NOT NULL,
    "requestId" TEXT NOT NULL,
    "approver"  TEXT NOT NULL,
    "decision"  TEXT NOT NULL,
    "reason"    TEXT NOT NULL DEFAULT '',
    "timestamp" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "ApprovalDecision_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "ApprovalDecision_requestId_idx" ON "ApprovalDecision"("requestId");
