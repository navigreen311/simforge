"""SQLAlchemy models (mapped to Prisma tables). Import all so metadata is complete."""

from src.models.agent import Agent
from src.models.base import Base
from src.models.department import Department

__all__ = ["Base", "Agent", "Department"]
