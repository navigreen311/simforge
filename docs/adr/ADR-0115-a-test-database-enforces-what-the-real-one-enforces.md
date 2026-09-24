# ADR-0115 — A test database enforces what the real one enforces

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-24 · **Built.**

---

## The ruling

> A test database enforces what the real one enforces.
>
> *Measured: outcome rows were inserted before the verdict they
> reference; Postgres refused, SQLite did not, and 13 tests plus CI
> passed on a build that could not write a single row.*

## What let it through

The suite builds an in-memory SQLite database from the SQLAlchemy mirror
(`Base.metadata.create_all`). Postgres runs the migrations. Two gaps:

1. **Foreign keys.** SQLite ignores them unless each connection sets
   `PRAGMA foreign_keys=ON`. Nothing set it.
2. **Constraints written only in SQL.** A CHECK or unique index in a
   migration and not in the model is never created in the test database.

## Measured, 24 September

The SQLAlchemy mirror compared with the dev database's real schema:

| Postgres enforces | Mirror had | Gap |
|---|---|---|
| Foreign keys | none enforced | all (closed by #207) |
| CHECK constraints (migrations) | 6 of 11 | 5 |
| Unique indexes (non-PK) | 27 of 32 | 5 |
| NOT NULL | all | 0 |
| Columns | all | 0 |
| Enum types, triggers | none exist | 0 |

The five CHECKs:
- `OperationCertification_score_is_labelled`
- `scenario_record_subject_and_claim_travel_together`
- `held_out_partition_status`
- `held_out_partition_scenario_class`
- `held_out_partition_verdict_value`

The five unique constraints:
- `AgentCert (agentId, forgeCap)`
- `DeptCert (departmentId, forgeContext)`
- `ForgeInstructionSet (forgeId, moduleId, contentHash)`
- `OntologyEntity (venture, name)`
- `Pack (packId, version)`

## Built

- **Foreign keys** (merged in #207): the pragma is set on every test
  connection, and `test_the_test_db_enforces_foreign_keys.py` pins it.
  It exposed 30 fixture-only violations and no `src/` write path.
- **The ten constraints** are mirrored in their models, with the same
  names Postgres uses. No test failed when they were added.
- **The guard**, `tests/unit/test_the_test_db_enforces_what_postgres_does.py`,
  reads every migration and fails if a CHECK or unique index (partial
  included) is not in the mirror. A later `DROP CONSTRAINT` is honoured.
  Its positive control and two mutations (removing one unique constraint,
  then one CHECK) each fail it.

## Tested

- Full suite: 1437 passed, 5 skipped. `ruff` clean.

## What this does not do

- Types. SQLite accepts a string in an integer column; Postgres does not.
  No failure has been traced to it. A Postgres-backed CI job would close
  it and is a separate cost.
- Behaviour Postgres has and SQLite lacks: `FOR UPDATE`, advisory locks,
  timestamp precision. These stay tested by source assertion, as today.
