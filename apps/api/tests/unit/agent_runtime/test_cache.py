"""Tests for the LLM response cache — all 4 modes."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.agent_runtime.cache import CacheMissError, LLMResponseCache

_REQ = {"provider": "ollama", "model": "m", "system": "s", "messages": [], "seed": 1}
_RESP = {"content": "hi", "tokens_input": 3, "tokens_output": 2, "model": "m", "provider": "ollama"}


def _cache(tmp_path: Path, mode: str) -> LLMResponseCache:
    return LLMResponseCache(cache_dir=str(tmp_path / "c"), mode=mode)


async def test_off_mode(tmp_path: Path) -> None:
    c = _cache(tmp_path, "off")
    assert await c.get(c.key_for(_REQ)) is None
    await c.put(_REQ, _RESP, "ollama", "m")  # no-op
    # even after put, off never serves
    assert await c.get(c.key_for(_REQ)) is None


async def test_record_then_read(tmp_path: Path) -> None:
    rec = _cache(tmp_path, "record")
    key = rec.key_for(_REQ)
    assert await rec.get(key) is None  # miss (no raise in record)
    await rec.put(_REQ, _RESP, "ollama", "m")
    assert (await rec.get(key))["content"] == "hi"

    # read mode serves the recorded entry but never writes
    rd = _cache(tmp_path, "read")
    assert (await rd.get(key))["content"] == "hi"
    await rd.put({**_REQ, "seed": 99}, _RESP, "ollama", "m")  # no-op
    assert await rd.get(rd.key_for({**_REQ, "seed": 99})) is None


async def test_replay_strict_hit_and_miss(tmp_path: Path) -> None:
    rec = _cache(tmp_path, "record")
    await rec.put(_REQ, _RESP, "ollama", "m")

    strict = _cache(tmp_path, "replay_strict")
    assert (await strict.get(strict.key_for(_REQ)))["content"] == "hi"  # hit
    with pytest.raises(CacheMissError):
        await strict.get(strict.key_for({**_REQ, "seed": 404}))  # miss raises


async def test_key_is_canonical(tmp_path: Path) -> None:
    c = _cache(tmp_path, "off")
    # Key is independent of dict insertion order.
    a = c.key_for({"a": 1, "b": 2})
    b = c.key_for({"b": 2, "a": 1})
    assert a == b


async def test_purge_unused(tmp_path: Path) -> None:
    rec = _cache(tmp_path, "record")
    await rec.put(_REQ, _RESP, "ollama", "m")
    key = rec.key_for(_REQ)
    assert rec.purge_unused({key}) == 0  # keep the active one
    assert rec.purge_unused(set()) == 1  # nothing active → removed
