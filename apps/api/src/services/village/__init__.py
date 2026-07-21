"""Village OS coupling — read-only (blueprint §C.6, ADR-0001)."""

from src.services.village.ccb_composer import CCBComposer
from src.services.village.reader import (
    VillageReader,
    VillageReaderError,
    VillageSchemaFingerprintMismatch,
)

__all__ = [
    "VillageReader",
    "VillageReaderError",
    "VillageSchemaFingerprintMismatch",
    "CCBComposer",
]
