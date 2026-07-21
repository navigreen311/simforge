"""Tests for OllamaProvider — request shape, temperature=0 pass-through, retry on 5xx."""

from __future__ import annotations

import httpx
import pytest

from src.services.agent_runtime.llm_client import OllamaProvider


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    real = httpx.AsyncClient

    def fake(*a, **k):
        return real(transport=httpx.MockTransport(handler), timeout=k.get("timeout"))

    monkeypatch.setattr(httpx, "AsyncClient", fake)


async def test_request_shape_and_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        import json

        seen["url"] = str(req.url)
        seen["body"] = json.loads(req.content)
        return httpx.Response(
            200,
            json={
                "message": {"content": "David Kim: on it."},
                "prompt_eval_count": 40,
                "eval_count": 18,
                "done_reason": "stop",
            },
        )

    _patch_client(monkeypatch, handler)
    p = OllamaProvider("http://localhost:11434", "llama3.1:8b")
    resp = await p.complete(
        system="You are David Kim, an AE.",
        messages=[{"role": "scenario", "content": "hi"}],
        temperature=0.0,
        seed=101,
    )
    assert resp.content == "David Kim: on it."
    assert resp.tokens_input == 40 and resp.tokens_output == 18 and resp.tokens == 58
    assert seen["url"].endswith("/api/chat")
    assert seen["body"]["options"]["temperature"] == 0.0
    assert seen["body"]["options"]["top_p"] == 1.0
    assert seen["body"]["options"]["seed"] == 101
    assert seen["body"]["messages"][0]["role"] == "system"


async def test_retry_on_5xx_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, json={"error": "overloaded"})
        return httpx.Response(200, json={"message": {"content": "ok"}, "eval_count": 1})

    _patch_client(monkeypatch, handler)
    # zero backoff for a fast test
    monkeypatch.setattr("asyncio.sleep", lambda *_a, **_k: _noop())
    p = OllamaProvider("http://localhost:11434", "m", max_retries=2)
    resp = await p.complete(system="s", messages=[], temperature=0.0)
    assert resp.content == "ok"
    assert calls["n"] == 2  # retried once


async def _noop() -> None:
    return None
