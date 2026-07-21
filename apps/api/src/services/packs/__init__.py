"""Pack ingestion service — validate a Pack directory and upsert it into the registry."""

from src.services.packs.ingestion import IngestionError, ingest_pack

__all__ = ["ingest_pack", "IngestionError"]
