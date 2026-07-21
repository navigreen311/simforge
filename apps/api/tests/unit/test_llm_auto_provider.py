"""`auto` LLM-provider resolution — ollama-if-reachable-else-stub (ADR-0023), hermetic.

No real Ollama here: reachability is monkeypatched so both branches are exercised deterministically.
"""

from __future__ import annotations

import pytest

from src.config import settings
from src.services.agent_runtime.llm_client import (
    OllamaProvider,
    StubProvider,
    get_agent_llm,
    get_judge_llm,
    reset_reachability_cache,
    resolve_provider,
)


def test_explicit_providers_pass_through() -> None:
    assert resolve_provider("stub") == "stub"
    assert resolve_provider("ollama") == "ollama"
    assert resolve_provider("anthropic") == "anthropic"


def test_auto_resolves_to_ollama_when_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.services.agent_runtime.llm_client._ollama_reachable", lambda *a, **k: True
    )
    assert resolve_provider("auto") == "ollama"


def test_auto_resolves_to_stub_when_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.services.agent_runtime.llm_client._ollama_reachable", lambda *a, **k: False
    )
    assert resolve_provider("auto") == "stub"


def test_get_judge_llm_auto_picks_ollama_when_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_judge_provider", "auto")
    monkeypatch.setattr(
        "src.services.agent_runtime.llm_client._ollama_reachable", lambda *a, **k: True
    )
    judge = get_judge_llm()
    assert isinstance(judge.inner, OllamaProvider)  # type: ignore[attr-defined]
    assert judge.inner.model == settings.ollama_judge_model  # type: ignore[attr-defined]


def test_get_judge_llm_auto_falls_back_to_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_judge_provider", "auto")
    monkeypatch.setattr(
        "src.services.agent_runtime.llm_client._ollama_reachable", lambda *a, **k: False
    )
    judge = get_judge_llm()
    assert isinstance(judge.inner, StubProvider)  # type: ignore[attr-defined]


def test_get_agent_llm_auto_falls_back_to_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "auto")
    monkeypatch.setattr(
        "src.services.agent_runtime.llm_client._ollama_reachable", lambda *a, **k: False
    )
    assert isinstance(get_agent_llm().inner, StubProvider)  # type: ignore[attr-defined]


def test_default_judge_provider_is_stub_no_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    # The CI/default path must never probe — resolve stub without touching reachability.
    def _boom(*a: object, **k: object) -> bool:
        raise AssertionError("reachability probed on the default (stub) path")

    monkeypatch.setattr("src.services.agent_runtime.llm_client._ollama_reachable", _boom)
    assert settings.llm_judge_provider == "stub"  # default unchanged (hermetic CI)
    assert isinstance(get_judge_llm().inner, StubProvider)  # type: ignore[attr-defined]


def test_reachability_cache_probes_once(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_reachability_cache()
    calls = {"n": 0}

    def _fake_urlopen(*a: object, **k: object):  # noqa: ANN202
        calls["n"] += 1
        raise OSError("refused")

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    from src.services.agent_runtime.llm_client import _ollama_reachable

    assert _ollama_reachable("http://localhost:11434") is False
    assert _ollama_reachable("http://localhost:11434") is False  # cached, no 2nd probe
    assert calls["n"] == 1
    reset_reachability_cache()
