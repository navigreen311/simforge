"""LLM response cache for hermetic tests (Path A / ADR-0008).

Modes (settings.llm_cache_mode):
- off            : never serves/writes — always live
- read           : serve if present, else fall through to live (no writes)
- record         : serve if present, else live + write to disk
- replay_strict  : serve if present, else raise CacheMissError (CI + unit default)

Keys are sha256(canonicalize_json(request)) — see ADR-0009 — so equal requests always hit
the same entry. Storage is sharded: {cache_dir}/{key[:2]}/{key}.json.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from src.config import settings
from src.utils.hashing import sha256_hex
from src.utils.time import utcnow


class CacheMissError(RuntimeError):
    """Raised in replay_strict mode when a request key is not in the cache."""


class LLMResponseCache:
    def __init__(self, cache_dir: str | None = None, mode: str | None = None) -> None:
        self.cache_dir = Path(cache_dir or settings.llm_cache_dir)
        self.mode = mode or settings.llm_cache_mode
        self._lock = asyncio.Lock()

    # -- key + paths ------------------------------------------------------

    def key_for(self, request: dict) -> str:
        return sha256_hex(request)

    def _path(self, key: str) -> Path:
        return self.cache_dir / key[:2] / f"{key}.json"

    # -- get / put --------------------------------------------------------

    async def get(self, request_key: str) -> dict | None:
        if self.mode == "off":
            return None
        path = self._path(request_key)
        async with self._lock:
            if path.exists():
                entry = json.loads(path.read_text(encoding="utf-8"))
                return entry["response"]
        if self.mode == "replay_strict":
            raise CacheMissError(
                f"LLM cache miss for key {request_key[:12]}… in replay_strict mode. "
                f"Populate fixtures with scripts/populate-llm-cache.py."
            )
        return None

    async def put(self, request: dict, response: dict, provider: str, model: str) -> None:
        if self.mode not in ("record",):
            return
        key = self.key_for(request)
        path = self._path(key)
        entry = {
            "request": request,
            "response": response,
            "recorded_at": utcnow().isoformat(),
            "provider": provider,
            "model": model,
        }
        async with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(entry, indent=2, sort_keys=True), encoding="utf-8")

    # -- maintenance ------------------------------------------------------

    def purge_unused(self, active_keys: set[str]) -> int:
        """Delete cache files whose key is not in `active_keys`. Returns count removed."""
        removed = 0
        if not self.cache_dir.exists():
            return 0
        for shard in self.cache_dir.iterdir():
            if not shard.is_dir():
                continue
            for f in shard.glob("*.json"):
                if f.stem not in active_keys:
                    f.unlink()
                    removed += 1
        return removed
