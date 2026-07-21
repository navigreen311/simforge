"""Tests for CachedLLMProvider — cache short-circuits the inner provider per mode."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.agent_runtime.cache import CacheMissError, LLMResponseCache
from src.services.agent_runtime.llm_client import CachedLLMProvider, LLMProvider, LLMResponse


class CountingProvider(LLMProvider):
    name = "counting"
    model = "count-1"

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, *, system, messages, temperature=0.0, max_tokens=2048, **kwargs):
        self.calls += 1
        return LLMResponse(
            content=f"live-{self.calls}", tokens_output=5, provider="counting", model="count-1"
        )

    async def health_check(self):
        return {"ok": True}


async def test_record_then_replay_hits_cache(tmp_path: Path) -> None:
    inner = CountingProvider()
    rec = CachedLLMProvider(inner, LLMResponseCache(str(tmp_path), "record"), purpose="judge")
    r1 = await rec.complete(system="s", messages=[], seed=1)
    assert r1.content == "live-1" and inner.calls == 1

    # replay_strict on same request → served from cache, inner NOT called again
    replay = CachedLLMProvider(inner, LLMResponseCache(str(tmp_path), "replay_strict"), "judge")
    r2 = await replay.complete(system="s", messages=[], seed=1)
    assert r2.content == "live-1" and r2.cached is True and inner.calls == 1


async def test_replay_strict_miss_raises(tmp_path: Path) -> None:
    inner = CountingProvider()
    replay = CachedLLMProvider(inner, LLMResponseCache(str(tmp_path), "replay_strict"), "judge")
    with pytest.raises(CacheMissError):
        await replay.complete(system="nope", messages=[], seed=1)


async def test_off_mode_always_live(tmp_path: Path) -> None:
    inner = CountingProvider()
    off = CachedLLMProvider(inner, LLMResponseCache(str(tmp_path), "off"), "judge")
    await off.complete(system="s", messages=[], seed=1)
    await off.complete(system="s", messages=[], seed=1)
    assert inner.calls == 2  # no caching
