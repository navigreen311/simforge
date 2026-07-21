"""Async SQLAlchemy engine + session (blueprint §A.5 `db.py`). See ADR-0003.

Prisma owns the schema/migrations; the Python runtime reads/writes via SQLAlchemy 2.0
async, with models mapped explicitly to Prisma's table/column names.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import settings

engine = create_async_engine(
    settings.sqlalchemy_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async DB session."""
    async with SessionLocal() as session:
        yield session


async def dispose_engine() -> None:
    await engine.dispose()
