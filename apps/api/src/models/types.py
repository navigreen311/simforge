"""Shared column types.

`StrArray` renders as Postgres text[] (matching Prisma `String[]`) but falls back to
JSON on SQLite so the hermetic test DB works without Postgres (see conftest / ADR-0003).
"""

from __future__ import annotations

from sqlalchemy import ARRAY, JSON, String

StrArray = ARRAY(String).with_variant(JSON(), "sqlite")
