"""Every exam call starts from a clean cache, or the exam does not run (B135).

Ivan Green, 18 October 2026. Ollama keeps a prompt cache, and the same prompt at the same seed gave
a different answer depending on what the cache held - three answers at temperature 0.0, one per
state. Only a cold load repeats whatever ran before. So the exam's provider unloads the model
(POST keep_alive 0), waits for `/api/ps` to be empty, then calls; and when it cannot, the exam
refuses rather than grading what it could not measure.
"""

from __future__ import annotations

import json

import httpx
import pytest

from src.models.submitted_answer import SubmittedProbeAnswer
from src.services.agent_runtime import llm_client
from src.services.agent_runtime.llm_client import ColdStartFailed, OllamaProvider, get_exam_llm
from src.services.operation.battery import run_module_battery
from src.services.operation.partition_grading import ModulePlan, put_partition
from src.services.operation.submitted_answers import record_submitted_answer
from tests.unit.test_held_out_authoring import PORTFOLIO_HEALTH_NEVER_DO
from tests.unit.test_operation_battery import _runtime

COLD_NS = 2_800_000_000
WARM_NS = 5_000_000


class _Ollama:
    """An Ollama that answers from a script and records every request, in order."""

    def __init__(self, *, ps_after_unload=((),), load_ns=(COLD_NS,), unload_status=200) -> None:
        self.ps = list(ps_after_unload)
        self.load_ns = list(load_ns)
        self.unload_status = unload_status
        self.seen: list[tuple[str, dict | None]] = []

    def handler(self, req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content) if req.content else None
        self.seen.append((req.url.path, body))
        if req.url.path == "/api/generate":
            return httpx.Response(self.unload_status, json={"done": True})
        if req.url.path == "/api/ps":
            names = self.ps.pop(0) if len(self.ps) > 1 else self.ps[0]
            return httpx.Response(200, json={"models": [{"name": n} for n in names]})
        load = self.load_ns.pop(0) if len(self.load_ns) > 1 else self.load_ns[0]
        return httpx.Response(
            200,
            json={
                "message": {"content": "ACT: PROCEED"},
                "prompt_eval_count": 4415,
                "eval_count": 60,
                "load_duration": load,
            },
        )

    def paths(self) -> list[str]:
        return [p for p, _ in self.seen]


@pytest.fixture
def ollama(monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    holder: dict = {}
    real = httpx.AsyncClient

    def fake(*a, **k):
        return real(transport=httpx.MockTransport(holder["o"].handler), timeout=k.get("timeout"))

    monkeypatch.setattr(httpx, "AsyncClient", fake)
    monkeypatch.setattr(llm_client, "COLD_UNLOAD_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(llm_client, "COLD_UNLOAD_POLL_SECONDS", 0.01)

    def install(o: _Ollama) -> _Ollama:
        holder["o"] = o
        return o

    return install


def _cold() -> OllamaProvider:
    return OllamaProvider("http://localhost:11434", "phi4:latest", cold_start=True)


async def test_the_model_is_unloaded_and_ps_empty_before_the_call(ollama) -> None:  # noqa: ANN001
    o = ollama(_Ollama(ps_after_unload=(("phi4:latest",), ())))
    response = await _cold().complete(system="s", messages=[], temperature=0.0, num_ctx=8192)

    assert o.paths() == ["/api/generate", "/api/ps", "/api/ps", "/api/chat"]
    assert o.seen[0][1] == {"model": "phi4:latest", "keep_alive": 0}
    assert response.cold_start is True
    assert response.load_ms == 2800
    assert response.tokens_input == 4415


async def test_ps_that_never_empties_refuses_and_asks_nothing(ollama) -> None:  # noqa: ANN001
    o = ollama(_Ollama(ps_after_unload=(("phi4:latest",),)))
    with pytest.raises(ColdStartFailed, match="still lists phi4:latest"):
        await _cold().complete(system="s", messages=[], temperature=0.0)
    assert "/api/chat" not in o.paths()


async def test_an_unload_ollama_refuses_is_a_refusal(ollama) -> None:  # noqa: ANN001
    o = ollama(_Ollama(unload_status=500))
    with pytest.raises(ColdStartFailed, match="could not unload phi4:latest"):
        await _cold().complete(system="s", messages=[], temperature=0.0)
    assert "/api/chat" not in o.paths()


async def test_a_warm_answer_is_discarded_and_the_call_made_again(ollama) -> None:  # noqa: ANN001
    """Someone loaded the model between the unload and the call: that answer read their cache."""
    o = ollama(_Ollama(load_ns=(WARM_NS, COLD_NS)))
    response = await _cold().complete(system="s", messages=[], temperature=0.0)

    assert o.paths().count("/api/generate") == 2
    assert o.paths().count("/api/chat") == 2
    assert response.cold_start is True and response.load_ms == 2800


async def test_always_warm_refuses_after_the_attempts(ollama) -> None:  # noqa: ANN001
    o = ollama(_Ollama(load_ns=(WARM_NS,)))
    with pytest.raises(ColdStartFailed, match="already loaded"):
        await _cold().complete(system="s", messages=[], temperature=0.0)
    assert o.paths().count("/api/chat") == llm_client.COLD_START_ATTEMPTS


async def test_a_provider_that_is_not_the_exams_never_unloads(ollama) -> None:  # noqa: ANN001
    o = ollama(_Ollama())
    plain = OllamaProvider("http://localhost:11434", "phi4:latest")
    response = await plain.complete(system="s", messages=[], temperature=0.7)

    assert o.paths() == ["/api/chat"]
    assert response.cold_start is None and response.load_ms is None


def test_the_exams_provider_starts_cold() -> None:
    assert get_exam_llm().inner.cold_start is True


def _refusing(system: str, prompt: str) -> str:
    raise ColdStartFailed("could not unload phi4:latest")


async def test_a_held_out_probe_does_not_turn_a_refusal_into_not_run() -> None:
    """A provider failure is NOT_RUN for that probe; a cold-start failure is the exam refusing."""
    runtime, _ = _runtime(_refusing)
    with pytest.raises(ColdStartFailed):
        await run_module_battery(
            module_id="portfolio_health",
            agent_id="agent-under-test",
            never_do=PORTFOLIO_HEALTH_NEVER_DO,
            runtime=runtime,
        )


async def test_a_partition_probe_does_not_either() -> None:
    from src.services.operation.held_out import author_for_module

    plan = ModulePlan(
        "portfolio_health",
        tuple(author_for_module("portfolio_health", PORTFOLIO_HEALTH_NEVER_DO)),
        PORTFOLIO_HEALTH_NEVER_DO,
    )
    runtime, _ = _runtime(_refusing)
    with pytest.raises(ColdStartFailed):
        await put_partition(agent_id="agent-under-test", plans=[plan], runtime=runtime)


class _Session:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, row) -> None:  # noqa: ANN001
        self.added.append(row)


def test_a_stored_answer_records_its_cold_start_beside_its_tokens() -> None:
    session = _Session()
    record_submitted_answer(
        session,  # type: ignore[arg-type]
        run_ref="ref",
        forge_id="cre-forge",
        module_id="comp_analysis",
        instruction_content_hash="h",
        scenario_ref="comp_analysis#escalation_required#3",
        scenario_class="escalation_required",
        ordinal=3,
        attempt=0,
        seed=0,
        verdict="PASS",
        reasons=[],
        answer_text="ACT: ESCALATE",
        prompt_eval_count=4429,
        eval_count=60,
        num_ctx=8192,
        cold_start=True,
        load_ms=2760,
    )
    (row,) = session.added
    assert isinstance(row, SubmittedProbeAnswer)
    assert (row.promptEvalCount, row.coldStart, row.loadMs) == (4429, True, 2760)
