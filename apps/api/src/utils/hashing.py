"""Canonicalization + hashing (ADR-0009).

Every hash-dependent operation (LLM cache keys, CCB content hashes, CertSnapshot signing,
lineage dedup) must canonicalize first so equal *values* always produce equal *bytes* —
independent of key order, whitespace, float formatting, or datetime tz/precision coercion.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any


def _default(o: Any) -> Any:
    if isinstance(o, datetime):
        # Naive UTC, millisecond precision (matches Prisma timestamp(3); see ADR-0007).
        dt = o
        if dt.tzinfo is not None:
            from datetime import UTC

            dt = dt.astimezone(UTC).replace(tzinfo=None)
        dt = dt.replace(microsecond=(dt.microsecond // 1000) * 1000)
        return dt.isoformat()
    if isinstance(o, float):
        # Stable short-form float encoding (repr gives shortest round-trip in py3).
        return repr(o)
    return str(o)


def canonicalize_json(obj: Any) -> str:
    """Deterministic JSON string: sorted keys, no whitespace, stable float/datetime encoding."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=_default)


def sha256_hex(obj: Any) -> str:
    """SHA-256 hex digest of the canonical JSON encoding of `obj`."""
    return hashlib.sha256(canonicalize_json(obj).encode("utf-8")).hexdigest()
