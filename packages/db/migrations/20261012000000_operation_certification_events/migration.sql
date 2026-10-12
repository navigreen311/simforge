-- ADR-0158: an OperationCertification's state change is recorded, append-only.
--
-- OperationCertification."state" is overwritten on revocation. This table
-- keeps the prior state, the actor and the reason. Rows are never updated
-- or deleted: a trigger refuses both, for every role including the owner.
-- Idempotent.
CREATE TABLE IF NOT EXISTS "OperationCertificationEvent" (
    "id" TEXT NOT NULL,
    "operationCertificationId" TEXT NOT NULL,
    "event" TEXT NOT NULL,
    "fromState" TEXT NOT NULL,
    "toState" TEXT NOT NULL,
    "actor" TEXT NOT NULL,
    "reason" TEXT NOT NULL,
    "at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "OperationCertificationEvent_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "OperationCertificationEvent_operationCertificationId_fkey"
        FOREIGN KEY ("operationCertificationId") REFERENCES "OperationCertification"("id")
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "operation_certification_event_event" CHECK ("event" IN ('revoked'))
);
CREATE INDEX IF NOT EXISTS "OperationCertificationEvent_operationCertificationId_idx"
    ON "OperationCertificationEvent"("operationCertificationId");

CREATE OR REPLACE FUNCTION operation_certification_event_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'OperationCertificationEvent is append-only (ADR-0158)';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS operation_certification_event_append_only
    ON "OperationCertificationEvent";
CREATE TRIGGER operation_certification_event_append_only
    BEFORE UPDATE OR DELETE ON "OperationCertificationEvent"
    FOR EACH ROW EXECUTE FUNCTION operation_certification_event_append_only();
