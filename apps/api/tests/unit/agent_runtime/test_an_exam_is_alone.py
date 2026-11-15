"""An exam is alone on the model from its first call to its last, or it is NOT RUN (ADR-0167).

Ivan Green, 14 November 2026: a second phi4 caller changed 33 of 57 answers while every exam call
still loaded the model cold. Ollama's request log is the evidence: the exam counts the model
requests it sent, and any more in the log between its first and last call voids it.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from src.services.agent_runtime import llm_client
from src.services.agent_runtime.llm_client import (
    AnotherPhi4Caller,
    CachedLLMProvider,
    ColdStartFailed,
    OllamaProvider,
)
from src.services.agent_runtime.request_log import RequestLog, Watch
from src.services.agent_runtime.runtime import begin_exam, end_exam

COLD_NS = 2_800_000_000


def gin(path: str, method: str = "POST") -> str:
    return (
        f"[GIN] 2026/11/14 - 09:55:23 | 200 |    2.0068068s |       127.0.0.1 | {method}     "
        f'"{path}"\n'
    )


class _Ollama:
    """Answers like Ollama and, like Ollama, writes one [GIN] line per request it served."""

    def __init__(self, log: Path) -> None:
        self.log = log
        self.others_on_call: dict[int, int] = {}  # on the n-th exam chat, this many other requests
        self.chats = 0

    def _write(self, line: str) -> None:
        with self.log.open("a", encoding="utf-8") as f:
            f.write(line)

    def handler(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path == "/api/ps":
            self._write(gin("/api/ps", "GET"))
            return httpx.Response(200, json={"models": []})
        self._write(gin(path))
        if path == "/api/generate":
            return httpx.Response(200, json={"done": True})
        self.chats += 1
        for _ in range(self.others_on_call.get(self.chats, 0)):
            self._write(gin("/api/chat"))  # Village speech, mid-exam
        return httpx.Response(
            200,
            json={
                "message": {"content": "ACT: PROCEED"},
                "eval_count": 9,
                "load_duration": COLD_NS,
            },
        )


@pytest.fixture
def ollama(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):  # noqa: ANN201
    log = tmp_path / "server.log"
    log.write_text(gin("/api/chat") + gin("/api/tags", "GET"), encoding="utf-8")  # earlier traffic
    o = _Ollama(log)
    real = httpx.AsyncClient

    def fake(*a, **k):
        return real(transport=httpx.MockTransport(o.handler), timeout=k.get("timeout"))

    monkeypatch.setattr(httpx, "AsyncClient", fake)
    monkeypatch.setattr(llm_client, "COLD_UNLOAD_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(llm_client, "COLD_UNLOAD_POLL_SECONDS", 0.01)
    return o


def _exam(log: Path | None) -> OllamaProvider:
    return OllamaProvider(
        "http://localhost:11434", "phi4:latest", cold_start=True, request_log=RequestLog(log)
    )


async def _calls(p, n: int) -> None:  # noqa: ANN001
    for _ in range(n):
        await p.complete(system="s", messages=[], temperature=0.0)


async def test_an_exam_that_was_alone_ends_quietly(ollama) -> None:  # noqa: ANN001
    p = _exam(ollama.log)
    begin_exam(p)
    await _calls(p, 4)
    await end_exam(p)  # no raise: nobody else asked Ollama for anything


async def test_another_caller_mid_exam_voids_it_at_the_next_call(ollama) -> None:  # noqa: ANN001
    ollama.others_on_call = {2: 1}
    p = _exam(ollama.log)
    begin_exam(p)
    with pytest.raises(AnotherPhi4Caller, match="another phi4 caller during the exam") as raised:
        await _calls(p, 4)
    assert isinstance(raised.value, ColdStartFailed), "every caller already refuses on these"
    assert ollama.chats == 2, "voided at once, no call after it"


async def test_another_caller_on_the_last_call_voids_it_at_the_end(ollama) -> None:  # noqa: ANN001
    """A request that ends after the exam's last call is caught by `end_exam`'s settled read."""
    p = _exam(ollama.log)
    begin_exam(p)
    await _calls(p, 3)
    with ollama.log.open("a", encoding="utf-8") as f:
        f.write(gin("/api/generate"))  # it ended as the exam's last call did
    with pytest.raises(AnotherPhi4Caller):
        await end_exam(p)


async def test_traffic_that_runs_no_model_is_not_another_caller(ollama) -> None:  # noqa: ANN001
    p = _exam(ollama.log)
    begin_exam(p)
    await _calls(p, 2)
    with ollama.log.open("a", encoding="utf-8") as f:
        f.write(gin("/api/tags", "GET") + gin("/api/show") + gin("/api/ps", "GET"))
    await _calls(p, 1)
    await end_exam(p)


async def test_traffic_before_the_exam_is_not_during_it(ollama) -> None:  # noqa: ANN001
    p = _exam(ollama.log)
    with ollama.log.open("a", encoding="utf-8") as f:
        f.write(gin("/api/chat") * 5)
    begin_exam(p)
    await _calls(p, 2)
    await end_exam(p)


async def test_no_log_to_read_is_not_a_pass(ollama, tmp_path: Path) -> None:  # noqa: ANN001
    p = _exam(tmp_path / "missing.log")
    with pytest.raises(AnotherPhi4Caller, match="cannot be told"):
        await _calls(p, 1)
    unset = OllamaProvider("http://x", "phi4:latest", cold_start=True, request_log=RequestLog(None))
    with pytest.raises(AnotherPhi4Caller, match="OLLAMA_REQUEST_LOG"):
        await _calls(unset, 1)


async def test_a_log_that_shrank_is_not_a_pass(ollama) -> None:  # noqa: ANN001
    p = _exam(ollama.log)
    begin_exam(p)
    await _calls(p, 2)
    ollama.log.unlink()  # Ollama restarted and began a new log
    ollama.log.write_text(gin("/api/tags", "GET") * 9, encoding="utf-8")
    with pytest.raises(AnotherPhi4Caller, match="cannot be told"):
        await end_exam(p)


async def test_a_new_exam_forgets_the_last_ones_watch(ollama) -> None:  # noqa: ANN001
    p = _exam(ollama.log)
    begin_exam(p)
    await _calls(p, 2)
    with ollama.log.open("a", encoding="utf-8") as f:
        f.write(gin("/api/chat"))  # between two exams, not during either
    begin_exam(p)
    await _calls(p, 2)
    await end_exam(p)


async def test_the_cache_wrapper_passes_the_watch_through(ollama) -> None:  # noqa: ANN001
    from src.services.agent_runtime.cache import LLMResponseCache

    ollama.others_on_call = {1: 2}
    wrapped = CachedLLMProvider(_exam(ollama.log), LLMResponseCache(mode="off"))
    begin_exam(wrapped)
    with pytest.raises(AnotherPhi4Caller):
        await _calls(wrapped, 2)


async def test_a_provider_that_watches_nothing_is_left_alone() -> None:
    class Scripted:
        pass

    begin_exam(Scripted())  # type: ignore[arg-type]
    await end_exam(Scripted())  # type: ignore[arg-type]


def test_the_log_reader_counts_model_requests_only(tmp_path: Path) -> None:
    log = tmp_path / "server.log"
    log.write_text("", encoding="utf-8")
    w = Watch(log, 0)
    log.write_text(
        gin("/api/chat")
        + gin("/api/generate")
        + gin("/api/embed")
        + gin("/api/ps", "GET")
        + gin("/api/tags", "GET")
        + gin("/api/show")
        + 'time=2026-11-14 level=INFO msg="llama runner started"\n'
        + gin("/api/chat").rstrip("\n"),  # still being written: counted next time
        encoding="utf-8",
    )
    assert w.model_requests() == 3


def test_the_exams_provider_watches_ollamas_own_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\someone\AppData\Local")
    exam = llm_client.get_exam_llm().inner
    assert exam.cold_start is True and exam.request_log is not None
    assert str(exam.request_log.path).replace("\\", "/").endswith("Ollama/server.log")
    assert json.dumps(str(exam.request_log.path))  # a plain path, nothing secret in it
