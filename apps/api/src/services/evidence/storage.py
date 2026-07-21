"""Evidence storage (blueprint §C.5).

Dev writes an evidence bundle to the local filesystem and returns a `file://` ref. In
staging/prod this is S3 with signed URLs + tiered lifecycle (same return contract).
"""

from __future__ import annotations

import json
from pathlib import Path

from src.config import settings


def store_evidence_bundle(bundle_id: str, bundle: dict) -> str:
    """Persist an evidence bundle and return its storage reference (URI)."""
    root = Path(settings.evidence_local_path)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{bundle_id}.json"
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return path.resolve().as_uri()
