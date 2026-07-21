"""Tests for AnthropicProvider — request shape (anthropic client mocked)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.services.agent_runtime.llm_client import AnthropicProvider


async def test_anthropic_request_and_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    class FakeMessages:
        async def create(self, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text="Judged: 0.82")],
                usage=SimpleNamespace(input_tokens=120, output_tokens=15),
                stop_reason="end_turn",
            )

    class FakeClient:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

    import anthropic

    monkeypatch.setattr(anthropic, "AsyncAnthropic", FakeClient)

    p = AnthropicProvider("sk-ant-test", "claude-3-5-sonnet-20241022")
    resp = await p.complete(
        system="You are a judge.",
        messages=[{"role": "agent", "content": "hi"}],
        temperature=0.0,
        max_tokens=512,
    )
    assert resp.content == "Judged: 0.82"
    assert resp.tokens_input == 120 and resp.tokens_output == 15
    assert resp.provider == "anthropic"
    assert seen["model"] == "claude-3-5-sonnet-20241022"
    assert seen["temperature"] == 0.0 and seen["top_p"] == 1.0
    assert seen["system"] == "You are a judge."
    assert seen["messages"][0]["role"] == "assistant"  # agent → assistant
