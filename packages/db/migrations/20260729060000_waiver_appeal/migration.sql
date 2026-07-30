-- Waiver/exception registry + Appeal workflow (§11.5).
CREATE TABLE "Waiver" (
    "id"                   TEXT NOT NULL,
    "subject"              TEXT NOT NULL,
    "scope"                TEXT NOT NULL,
    "reason"               TEXT NOT NULL DEFAULT '',
    "compensatingControls" TEXT[] NOT NULL DEFAULT '{}',
    "status"               TEXT NOT NULL DEFAULT 'active',
    "grantedBy"            TEXT NOT NULL DEFAULT 'admin',
    "grantedAt"            TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expiresAt"            TIMESTAMP(3) NOT NULL,
    "revokedAt"            TIMESTAMP(3),
    CONSTRAINT "Waiver_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "Waiver_status_idx" ON "Waiver"("status");

CREATE TABLE "Appeal" (
    "id"                 TEXT NOT NULL,
    "targetType"         TEXT NOT NULL DEFAULT 'cert_decision',
    "targetId"           TEXT NOT NULL,
    "appellant"          TEXT NOT NULL,
    "grounds"            TEXT NOT NULL DEFAULT '',
    "originalApprover"   TEXT,
    "status"             TEXT NOT NULL DEFAULT 'open',
    "secondReviewer"     TEXT,
    "reviewerDecision"   TEXT,
    "resolutionNote"     TEXT NOT NULL DEFAULT '',
    "escalatedToFounder" BOOLEAN NOT NULL DEFAULT false,
    "createdAt"          TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "resolvedAt"         TIMESTAMP(3),
    CONSTRAINT "Appeal_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "Appeal_status_idx" ON "Appeal"("status");
