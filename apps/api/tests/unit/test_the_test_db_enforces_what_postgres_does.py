"""A test database enforces what the real one enforces (ADR-0115).

The suite builds its database from the SQLAlchemy mirror. Postgres runs the
migrations. A constraint in the second and not the first is one the suite
never sees fail - which is how 13 tests and CI passed a build whose every
outcome write Postgres refused.

So every CHECK and every unique index the migrations create must exist in
the mirror. Foreign keys are enforced by the connection pragma
(tests/conftest.py) and pinned in test_the_test_db_enforces_foreign_keys.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import CheckConstraint, UniqueConstraint

from src.models import Base

MIGRATIONS = Path(__file__).resolve().parents[4] / "packages" / "db" / "migrations"

_CHECK = re.compile(r'CONSTRAINT\s+"?(\w+)"?\s+CHECK', re.I)
_UNIQUE = re.compile(
    r'CREATE\s+UNIQUE\s+INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?"?(\w+)"?\s+ON\s+"?(\w+)"?\s*'
    r"(?:USING\s+\w+\s*)?\(([^)]*)\)\s*(WHERE[^;]*)?;",
    re.I,
)
#: Dropped by a later migration, so no longer enforced anywhere.
_DROPPED = re.compile(r'DROP\s+CONSTRAINT\s+(?:IF\s+EXISTS\s+)?"?(\w+)"?', re.I)


def _sql() -> list[str]:
    return [p.read_text(encoding="utf-8") for p in sorted(MIGRATIONS.glob("*/migration.sql"))]


def _migration_checks() -> set[str]:
    live: set[str] = set()
    for text in _sql():
        # Within one file a DROP ... IF EXISTS precedes the re-ADD, so order matters.
        for m in re.finditer(f"{_CHECK.pattern}|{_DROPPED.pattern}", text, re.I):
            if m.group(1):
                live.add(m.group(1))
            elif m.group(2) and m.group(2) in live:
                live.discard(m.group(2))
    return live


def _migration_uniques() -> set[tuple[str, tuple[str, ...], bool]]:
    out = set()
    for text in _sql():
        for _, table, cols, where in _UNIQUE.findall(text):
            names = tuple(sorted(c.strip().strip('"') for c in cols.split(",")))
            out.add((table, names, bool(where)))
    return out


def _mirror_checks() -> set[str]:
    return {
        c.name
        for t in Base.metadata.tables.values()
        for c in t.constraints
        if isinstance(c, CheckConstraint) and c.name
    }


def _mirror_uniques() -> set[tuple[str, tuple[str, ...], bool]]:
    out = set()
    for t in Base.metadata.tables.values():
        for col in t.columns:
            if col.unique:
                out.add((t.name, (col.name,), False))
        for con in t.constraints:
            if isinstance(con, UniqueConstraint):
                out.add((t.name, tuple(sorted(c.name for c in con.columns)), False))
        for idx in t.indexes:
            if idx.unique:
                partial = idx.dialect_options["postgresql"].get("where") is not None
                out.add((t.name, tuple(sorted(c.name for c in idx.columns)), partial))
    return out


def test_the_migrations_are_found() -> None:
    assert len(_sql()) > 40
    assert _migration_checks() and _migration_uniques()


def test_every_check_postgres_enforces_is_in_the_mirror() -> None:
    missing = sorted(_migration_checks() - _mirror_checks())
    assert not missing, (
        f"CHECK constraints the migrations create and the test database never enforces: "
        f"{missing}. Mirror each in its model's __table_args__ (ADR-0115)."
    )


def test_every_unique_index_postgres_enforces_is_in_the_mirror() -> None:
    mirror = _mirror_uniques()
    missing = sorted(u for u in _migration_uniques() if u not in mirror)
    assert not missing, (
        f"Unique indexes (table, columns, partial) the test database never enforces: "
        f"{missing}. Mirror each in its model (ADR-0115)."
    )


def test_the_guard_bites() -> None:
    """Positive control: a constraint only in SQL is reported."""
    fake = 'ALTER TABLE "X" ADD CONSTRAINT "only_in_sql" CHECK (1 = 1);'
    assert _CHECK.findall(fake) == ["only_in_sql"]
    assert "only_in_sql" not in _mirror_checks()
    fake_u = 'CREATE UNIQUE INDEX "X_a_key" ON "Agent"("a", "b") WHERE "a" = 1;'
    [(_, table, cols, where)] = _UNIQUE.findall(fake_u)
    assert (table, ("a", "b"), bool(where)) not in _mirror_uniques()
