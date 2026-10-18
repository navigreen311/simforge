"""The exam asks Ollama for its context window, and every answer records what it cost (B131).

Ivan Green, 17 October 2026. Ollama serves phi4 at 4096 tokens when a request names no `num_ctx`,
and the CRE Forge's comp_analysis 1.11.7 prompt is 4,307-4,415 phi4 tokens. Past the window the
runner discards half the prompt mid-answer and says nothing: the exam would grade an agent that
never read its manual. So the exam names the window on every call, the same value the Village
operator sends (AGENT_NUM_CTX), and every call's `prompt_eval_count` is recorded.
"""

from __future__ import annotations

import json

import httpx
import pytest

from src.config import settings
from src.models.submitted_answer import SubmittedProbeAnswer
from src.services.agent_runtime.llm_client import LLMResponse, OllamaProvider
from src.services.agent_runtime.runtime import AgentRuntime
from src.services.operation.submitted_answers import record_submitted_answer


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    real = httpx.AsyncClient

    def fake(*a, **k):
        return real(transport=httpx.MockTransport(handler), timeout=k.get("timeout"))

    monkeypatch.setattr(httpx, "AsyncClient", fake)


def _ollama(monkeypatch: pytest.MonkeyPatch, seen: list) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(json.loads(req.content))
        return httpx.Response(
            200, json={"message": {"content": "ok"}, "prompt_eval_count": 4415, "eval_count": 60}
        )

    _patch_client(monkeypatch, handler)


async def test_ollama_is_sent_the_window_the_caller_names(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list = []
    _ollama(monkeypatch, seen)
    p = OllamaProvider("http://localhost:11434", "phi4:latest")
    await p.complete(system="s", messages=[], temperature=0.7, num_ctx=8192)
    assert seen[0]["options"]["num_ctx"] == 8192


async def test_no_window_named_sends_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-exam caller that names none leaves the server default alone, as before."""
    seen: list = []
    _ollama(monkeypatch, seen)
    p = OllamaProvider("http://localhost:11434", "phi4:latest")
    await p.complete(system="s", messages=[], temperature=0.7)
    assert "num_ctx" not in seen[0]["options"]


def test_the_default_window_is_8192() -> None:
    """The value Ivan ruled, and the one the Village operator's AGENT_NUM_CTX defaults to."""
    assert settings.exam_num_ctx == 8192


class _Village:
    def __getattr__(self, name):
        def nothing(*_a, **_k):
            return {}

        return nothing


async def test_every_exam_turn_asks_for_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list = []
    _ollama(monkeypatch, seen)
    runtime = AgentRuntime(
        village_reader=_Village(),  # type: ignore[arg-type]
        provider=OllamaProvider("http://localhost:11434", "phi4:latest"),
        generation={"temperature": 0.7, "max_tokens": 4000},
    )
    response = await runtime.turn("victor_serath", [{"role": "scenario", "content": "go"}], 1)
    assert seen[0]["options"]["num_ctx"] == settings.exam_num_ctx
    assert seen[0]["options"]["num_predict"] == 4000
    # `prompt_eval_count` comes back as the response's input count, which the battery stores.
    assert response.tokens_input == 4415 and response.tokens_output == 60
    # And the window is part of what the exam ran under, so the model identity records it.
    assert runtime.exam_settings()["num_ctx"] == settings.exam_num_ctx


def test_a_village_declaration_of_the_window_wins() -> None:
    runtime = AgentRuntime(
        village_reader=_Village(),  # type: ignore[arg-type]
        provider=None,  # type: ignore[arg-type]
        generation={"temperature": 0.7, "max_tokens": 4000, "num_ctx": 16384},
    )
    assert runtime.exam_settings()["num_ctx"] == 16384


class _Session:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, row) -> None:
        self.added.append(row)


def test_a_stored_answer_carries_its_token_counts_and_window() -> None:
    session = _Session()
    record_submitted_answer(
        session,  # type: ignore[arg-type]
        run_ref="ref",
        forge_id="cre-forge",
        module_id="comp_analysis",
        instruction_content_hash="h",
        scenario_ref="comp_analysis#happy_path#5",
        scenario_class="happy_path",
        ordinal=5,
        attempt=0,
        seed=0,
        verdict="PASS",
        reasons=[],
        answer_text="ACT: PROCEED",
        prompt_eval_count=4415,
        eval_count=60,
        num_ctx=8192,
    )
    (row,) = session.added
    assert isinstance(row, SubmittedProbeAnswer)
    assert (row.promptEvalCount, row.evalCount, row.numCtx) == (4415, 60, 8192)


def test_llm_response_reports_prompt_eval_count_as_its_input() -> None:
    """The name the battery reads. Ollama's `prompt_eval_count` is `tokens_input`."""
    assert LLMResponse(content="", tokens_input=7).tokens_input == 7
