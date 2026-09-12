"""ADR-0054 — the examiner is named, resolvable, and never `auto`.

The defaults these assertions guard were previously `claude-3-5-sonnet-20241022`, which is retired:
a real call returns 404 `not_found_error`. It passed `health_check` — `bool(self.api_key)` — and
would have failed on the battery's first real call.

None of these tests reach the network. They assert the shape of what is configured, which is the
part that was wrong: a retired model ID is a configuration fact, and it was sitting in the default.
"""

from __future__ import annotations

from src.config import Settings
from src.services.agent_runtime.llm_client import rejects_sampling_params, resolve_provider

#: Retired or otherwise non-resolving IDs that have been in this repository's defaults.
RETIRED = frozenset({"claude-3-5-sonnet-20241022"})


def test_the_examiner_default_is_not_a_retired_model() -> None:
    s = Settings()
    assert s.anthropic_agent_model not in RETIRED
    assert s.anthropic_judge_model not in RETIRED


def test_the_examiner_default_is_the_ruled_model() -> None:
    """ADR-0054. Changing this is a ruling, not a tidy-up — it changes what certifies agents."""
    s = Settings()
    assert s.anthropic_agent_model == "claude-sonnet-5"
    assert s.anthropic_judge_model == "claude-sonnet-5"


def test_auto_never_resolves_to_anthropic() -> None:
    """Why the examiner must be named. `auto` picks Ollama or the stub and never the examiner, so a
    battery launched on `auto` measures whatever is running locally — which is how a scoreboard of
    the stub was once published as a measurement of a model."""
    assert resolve_provider("auto") in {"ollama", "stub"}
    assert resolve_provider("anthropic") == "anthropic"


def test_sampling_params_are_withheld_from_models_that_reject_them() -> None:
    """`temperature`/`top_p` are removed on the current generation and return a 400 — not a
    degraded request, a failed one. Sending them made every current Claude model unreachable."""
    for model in (
        "claude-sonnet-5",
        "claude-opus-5",
        "claude-opus-4-8",
        "claude-opus-4-7",
        "claude-fable-5-1",
    ):
        assert rejects_sampling_params(model), model
    for model in ("claude-haiku-4-5-20251001", "claude-sonnet-4-5-20250929", "llama3.1:8b"):
        assert not rejects_sampling_params(model), model
