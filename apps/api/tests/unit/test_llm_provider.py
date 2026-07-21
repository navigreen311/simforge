"""Unit tests for LLM provider selection + the Ollama provider (mocked HTTP)."""

from __future__ import annotations

import httpx
import pytest

from src.config import settings
from src.services.agent_runtime.llm_client import (
    OllamaProvider,
    StubProvider,
    get_llm_provider,
    to_ollama_messages,
)


def test_role_mapping_to_ollama() -> None:
    msgs = to_ollama_messages(
        "SYS",
        [
            {"role": "scenario", "content": "cold open"},
            {"role": "agent", "content": "hi"},
            {"role": "world", "content": "ok"},
        ],
    )
    assert msgs[0] == {"role": "system", "content": "SYS"}
    assert [m["role"] for m in msgs[1:]] == ["user", "assistant", "user"]


def test_provider_selection_default_is_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "stub")
    assert isinstance(get_llm_provider(), StubProvider)


def test_provider_selection_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_model", "llama3.1:8b")
    p = get_llm_provider()
    assert isinstance(p, OllamaProvider)
    assert p.model == "llama3.1:8b"


async def test_ollama_complete_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "David Kim: On it, confirming consent.",
                },
                "prompt_eval_count": 40,
                "eval_count": 18,
            },
        )

    real_client = httpx.AsyncClient

    def fake_client(*args, **kwargs):
        return real_client(transport=httpx.MockTransport(handler), timeout=kwargs.get("timeout"))

    monkeypatch.setattr(httpx, "AsyncClient", fake_client)

    provider = OllamaProvider("http://localhost:11434", "llama3.1:8b")
    resp = await provider.complete(
        system="You are David Kim, an Account Executive.",
        messages=[{"role": "scenario", "content": "A homeowner calls."}],
        seed=101,
    )
    assert resp.content == "David Kim: On it, confirming consent."
    assert resp.tokens == 58  # 40 + 18
    assert captured["url"].endswith("/api/chat")
    assert captured["body"]["model"] == "llama3.1:8b"
    assert captured["body"]["options"]["seed"] == 101
    assert captured["body"]["messages"][0]["role"] == "system"
