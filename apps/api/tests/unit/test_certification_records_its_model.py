"""A certification names the model that answered — and the two schemas agree it does.

`OperationCertification` records the version matrix a cert was earned under. Every part
of it describes the **exam**: which instructions, which Forge version, which rubric. None
described the **candidate**, so a row said *the agent passed* and could not say *the
agent, on this model, passed* — and swapping the model left it reading as current.

The second test here is the one worth keeping. This repo has **two** schemas: the Prisma
one that production migrates to, and the SQLAlchemy mirror that `conftest.py` builds the
test database from with `create_all`. **The suite only ever sees the mirror.** So a change
that edits the mirror and forgets the migration passes every other test in this file and
ships a column that does not exist in production — which is theoffice's blocking.md B26
exactly: the thing in git and the thing in force diverging, with a green board over it.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.models.operation_cert import OperationCertification

REPO = Path(__file__).resolve().parents[4]
SCHEMA = REPO / "packages" / "db" / "schema.prisma"
MIGRATIONS = REPO / "packages" / "db" / "migrations"


def test_the_sqlalchemy_mirror_carries_the_column():
    """The half the suite can see."""
    column = OperationCertification.__table__.columns.get("agentModel")
    assert column is not None, "OperationCertification has no agentModel column"
    # Nullable, and deliberately: a timed-out run got no answer and a department_context
    # unit is cleared by department state. Both legitimately have nothing to name, which
    # is why the requirement is enforced where the verdict class is known rather than by
    # a NOT NULL that would be wrong for two real row shapes.
    assert column.nullable


def test_the_prisma_schema_carries_it_too():
    """The half the suite CANNOT see, asserted by reading the file.

    Without this, editing only the SQLAlchemy mirror is a green board over a column
    production does not have.
    """
    text = SCHEMA.read_text(encoding="utf-8")
    model = re.search(r"model OperationCertification \{(.*?)\n\}", text, re.S)
    assert model, "OperationCertification not found in schema.prisma"
    assert re.search(r"^\s*agentModel\s+String\?", model.group(1), re.M), (
        "schema.prisma's OperationCertification has no optional agentModel. The "
        "SQLAlchemy mirror can carry a column the Prisma schema does not, and the test "
        "database is built from the mirror - so the suite would be green over a "
        "production schema that never got the column."
    )


def test_a_migration_actually_adds_it():
    """A schema edit without a migration is a schema nobody has applied.

    `schema.prisma` is the declared shape; the `migrations/` directory is what has been
    run. Asserting only the first would pass on a repo where the column exists in the
    declaration and in no database anywhere.
    """
    adds = [
        d.name
        for d in MIGRATIONS.iterdir()
        if d.is_dir()
        and (d / "migration.sql").exists()
        and "agentModel" in (d / "migration.sql").read_text(encoding="utf-8")
    ]
    assert adds, (
        "no migration under packages/db/migrations mentions agentModel. The column is "
        "declared and unapplied, which is the state that reads as done and is not."
    )
