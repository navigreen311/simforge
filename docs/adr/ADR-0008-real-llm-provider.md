# ADR-0008 — Real LLM provider integration (Path A)

**Status:** Accepted (2026-07-21) · Supersedes the summary ADR-0008 in `docs/DECISIONS.md`.

## Context
v1 shipped with a deterministic StubProvider everywhere. The scorecard's 3 **LLM-judge**
dimensions (P7 Customer Experience, C1 BREATH Coherence, C2 SOUL Stability) collapsed to
constants/heuristics — gate-correct but semantically hollow. Path A introduces real LLM signal
for those 3 dimensions while keeping v1 hermetic and CI green.

## Decision
- **Provider abstraction** (`services/agent_runtime/llm_client.py`): `LLMProvider` ABC with
  `complete()` / `health_check()`; concrete `StubProvider` (kept, now judge-aware),
  `OllamaProvider` (local `/api/chat`), `AnthropicProvider` (`claude-3-5-sonnet-20241022`).
  `CachedLLMProvider` decorates any provider with the hermetic cache.
- **Routing:** `LLM_PROVIDER` (agent runtime) and `LLM_JUDGE_PROVIDER` (evaluation) chosen at
  boot, independently. `get_agent_llm()` / `get_judge_llm()` factories. Every LLM call goes
  through a factory — no ad-hoc client instantiation.
- **Determinism:** all judge calls use `temperature=0, top_p=1`.
- **Cache** (`agent_runtime/cache.py`): sha256(canonicalize_json(request)) keys (ADR-0009),
  sharded storage, 4 modes (`off|read|record|replay_strict`). Populate real fixtures with
  `scripts/populate-llm-cache.py`; replay hermetically with `replay_strict`.
- **Judge scorers** (`dimensions/p7_cx.py`, `c1_breath_coherence.py`, `c2_soul_stability.py`):
  render a prompt (`evaluation/prompts/*.txt`), call the judge, parse JSON, retry once on
  invalid JSON, then fall back to 0.5 with a logged warning. Rationale is stored in scorecard
  annotations. P1–P6/P8 and C3–C7 are unchanged.
- **Token accounting + logging:** every `LLMResponse` increments
  `simforge_tokens_used_total{provider,model,purpose}` and logs provider/model/tokens/latency/cached.

## CI hermeticity (reasoned deviation from the brief)
The brief specified `LLM_CACHE_MODE=replay_strict` in CI. Because the **judge-aware StubProvider
returns deterministic valid JSON** (hash-derived, non-constant), CI achieves hermeticity in
**stub mode** (`LLM_PROVIDER=stub`, cache `off`) without brittle fixture-key coupling to prompt
text. The cache + `replay_strict` are exercised directly by unit tests
(`test_cache.py`, `test_cached_llm_provider.py`) and exist for **real-provider** hermetic replay.
Committed fixtures under `tests/fixtures/llm_cache/` are stub placeholders to be re-recorded
against Ollama/Anthropic via `populate-llm-cache.py`.

## Consequences
- P7/C1/C2 become meaningful with a real provider (`RUN_LIVE_LLM_TESTS=true` gates the live test).
- Token cost per run with Anthropic ≈ $0.08 (blueprint §K.1); Ollama is free/local.
- Scorecard determinism now relies on `temperature=0` + (for real providers) the cache.
- **No Constitution amendment needed** — only internal scoring machinery changed, not the rubric
  definition or thresholds. Threshold tuning is a Week-2 decision informed by
  `scripts/calibrate-judge-dims.py`.

## Cross-references
Blueprint §C.7 (LLM Client), §C.10 (Evaluation Engine), §I.1 (Unit Testing), §K.1 (Cost Model),
post-v1 Path A. Related: ADR-0007 (timestamp precision), ADR-0009 (canonicalization contract).
