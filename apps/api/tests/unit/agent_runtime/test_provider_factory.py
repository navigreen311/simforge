"""Tests for provider factory routing via LLM_PROVIDER / LLM_JUDGE_PROVIDER."""

from __future__ import annotations

import pytest

from src.config import settings
from src.services.agent_runtime.llm_client import (
    AnthropicProvider,
    CachedLLMProvider,
    OllamaProvider,
    StubProvider,
    get_agent_llm,
    get_judge_llm,
)


def test_default_is_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "stub")
    monkeypatch.setattr(settings, "llm_judge_provider", "stub")
    agent = get_agent_llm()
    judge = get_judge_llm()
    assert isinstance(agent, CachedLLMProvider) and isinstance(agent.inner, StubProvider)
    assert isinstance(judge.inner, StubProvider)


def test_ollama_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_agent_model", "llama3.1:8b")
    inner = get_agent_llm().inner
    assert isinstance(inner, OllamaProvider) and inner.model == "llama3.1:8b"


def test_anthropic_judge_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_judge_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_judge_model", "claude-3-5-sonnet-20241022")
    inner = get_judge_llm().inner
    assert isinstance(inner, AnthropicProvider)
    assert inner.model == "claude-3-5-sonnet-20241022"


def test_judge_provider_independent_of_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "stub")
    monkeypatch.setattr(settings, "llm_judge_provider", "ollama")
    assert isinstance(get_agent_llm().inner, StubProvider)
    assert isinstance(get_judge_llm().inner, OllamaProvider)
