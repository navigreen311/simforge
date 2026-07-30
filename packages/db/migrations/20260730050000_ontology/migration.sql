-- Knowledge Graph / Domain Ontology per venture (v1.1). The entities and relationships that define a
-- venture's world, so scenarios can be grounded in (and checked against) a real domain model.
CREATE TABLE "OntologyEntity" (
    "id"          TEXT NOT NULL,
    "venture"     TEXT NOT NULL,
    "name"        TEXT NOT NULL,
    "category"    TEXT NOT NULL DEFAULT 'concept',
    "description" TEXT NOT NULL DEFAULT '',
    "createdAt"   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "OntologyEntity_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "OntologyEntity_venture_name_key" ON "OntologyEntity"("venture", "name");

CREATE TABLE "OntologyRelation" (
    "id"         TEXT NOT NULL,
    "venture"    TEXT NOT NULL,
    "fromEntity" TEXT NOT NULL,
    "relation"   TEXT NOT NULL,
    "toEntity"   TEXT NOT NULL,
    "createdAt"  TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "OntologyRelation_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "OntologyRelation_venture_idx" ON "OntologyRelation"("venture");
