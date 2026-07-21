"""Ollama judge replays the committed cache in replay_strict — hermetic, runs in CI (ADR-0023).

Forces LLM_JUDGE_PROVIDER=ollama + LLM_CACHE_MODE=replay_strict against the committed fixture cache
(tests/fixtures/llm_cache/). No live Ollama: every judge call must hit a recorded entry, proving
the real-judge scores replay offline. This is the CI-safe embodiment of the acceptance check
"LLM_JUDGE_PROVIDER=ollama pytest passes with cache in replay_strict".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from src.config import settings
from src.services.agent_runtime.llm_client import get_judge_llm

REPO_ROOT = Path(__file__).resolve().parents[4]
SCENARIOS_YML = REPO_ROOT / "scripts" / "canonical_test_scenarios.yml"
# The script helpers live under scripts/; reuse build_ctx/score_all to match recorded requests.
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from _judge_scenarios import build_ctx, score_all  # noqa: E402


def _canonical_scenarios() -> list[dict]:
    return yaml.safe_load(SCENARIOS_YML.read_text(encoding="utf-8"))["scenarios"]


@pytest.fixture
def _ollama_replay(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "llm_judge_provider", "ollama")
    monkeypatch.setattr(settings, "llm_cache_mode", "replay_strict")


@pytest.mark.parametrize("scn", _canonical_scenarios(), ids=lambda s: s["id"])
async def test_canonical_scenario_replays_from_committed_cache(scn: dict, _ollama_replay) -> None:
    scores = await score_all(build_ctx(scn), get_judge_llm())
    # Every dim served from the committed real-Ollama cache, in range.
    assert scores["p7_cx"] is not None and 0.0 <= scores["p7_cx"] <= 1.0
    for dim in ("c1_breath", "c2_soul"):
        assert scores[dim] is None or 0.0 <= scores[dim] <= 1.0


async def test_weak_cx_scenario_scored_low_by_real_judge(_ollama_replay) -> None:
    # The signal that matters: the real judge (replayed) marks curt/weak handling far below stub.
    scn = next(s for s in _canonical_scenarios() if s["id"] == "gs_foundational_weak_cx")
    scores = await score_all(build_ctx(scn), get_judge_llm())
    assert scores["p7_cx"] <= 0.4  # recorded real-Ollama value was 0.20 (stub gives ~0.75-0.95)
