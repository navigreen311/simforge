"""LLM provider abstraction (blueprint §C.8, ADR-0008).

Providers: StubProvider (deterministic/offline, default; judge-aware), OllamaProvider (local),
AnthropicProvider (cloud). CachedLLMProvider wraps any of them with the hermetic cache.
Route via LLM_PROVIDER / LLM_JUDGE_PROVIDER. All judge calls use temperature=0 for determinism.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass

from src.config import settings
from src.services.agent_runtime.cache import LLMResponseCache
from src.telemetry.logging import get_logger
from src.telemetry.metrics import TOKENS_TOTAL

log = get_logger("llm")
_NAME_RE = re.compile(r"You are ([^,]+),")


@dataclass
class LLMResponse:
    content: str
    tokens_input: int = 0
    tokens_output: int = 0
    model: str = "unknown"
    provider: str = "unknown"
    finish_reason: str = "stop"
    latency_ms: int = 0
    cached: bool = False

    @property
    def tokens(self) -> int:  # backward-compatible total (used by the runner)
        return self.tokens_input + self.tokens_output


class LLMProvider(ABC):
    name: str = "abstract"
    model: str = "unknown"

    @abstractmethod
    async def complete(
        self,
        *,
        system: str,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs,
    ) -> LLMResponse: ...

    @abstractmethod
    async def health_check(self) -> dict: ...


# ═══════════════════════════════════════════════════════════════
# Role mapping (shared by real providers)
# ═══════════════════════════════════════════════════════════════


def to_chat_messages(system: str, messages: list[dict]) -> list[dict]:
    """Map SimForge transcript turns → chat roles (agent→assistant, scenario/world→user)."""
    out: list[dict] = [{"role": "system", "content": system}]
    for m in messages:
        role = "assistant" if m.get("role") == "agent" else "user"
        out.append({"role": role, "content": m.get("content", "")})
    return out


def _emit_tokens(resp: LLMResponse, purpose: str) -> None:
    TOKENS_TOTAL.labels(provider=resp.provider, model=resp.model, purpose=purpose).inc(
        resp.tokens_input + resp.tokens_output
    )


# ═══════════════════════════════════════════════════════════════
# StubProvider (deterministic, offline). Judge-aware.
# ═══════════════════════════════════════════════════════════════


class StubProvider(LLMProvider):
    name = "stub"
    model = "stub-llm"

    _OPENERS = [
        "Thanks for the context.",
        "Understood.",
        "Let me make sure I have this right.",
        "Appreciate you flagging that.",
        "Okay, here's where I'd take this.",
    ]
    _MOVES = [
        "First, I'll confirm the key facts before committing to anything.",
        "I want to keep this compliant, so I'll verify consent and scope up front.",
        "Let me address the immediate concern and then lay out next steps.",
        "I'll be transparent about the tradeoffs so we're aligned.",
        "I'll de-escalate, gather what I need, and propose a clear path.",
    ]
    _CLOSERS = [
        "Does that work for you?",
        "I'll proceed on that basis unless you'd like to adjust.",
        "Let me know if anything there gives you pause.",
        "I'll document this and follow up.",
        "That should get us to a good outcome.",
    ]

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs,
    ) -> LLMResponse:
        purpose = kwargs.get("purpose", "agent")
        if purpose == "judge" or "Respond ONLY with" in system:
            return self._judge(system, messages)
        return self._agent(system, messages, int(kwargs.get("seed", 0)))

    def _agent(self, system: str, messages: list[dict], seed: int) -> LLMResponse:
        turn = len(messages)
        rng = random.Random((seed << 8) ^ turn)
        name_match = _NAME_RE.search(system)
        name = name_match.group(1).strip() if name_match else "The agent"
        last = messages[-1]["content"] if messages else ""
        snippet = " ".join(last.split()[:8])
        parts = [rng.choice(self._OPENERS)]
        parts.append(
            f'Regarding "{snippet}…", {rng.choice(self._MOVES).lower()}'
            if snippet
            else rng.choice(self._MOVES)
        )
        if turn >= 5:
            parts.append("I think we've reached a workable resolution.")
        parts.append(rng.choice(self._CLOSERS))
        content = f"{name}: " + " ".join(parts)
        out = max(1, int(len(content.split()) * 1.3))
        return LLMResponse(
            content=content,
            tokens_input=turn * 20,
            tokens_output=out,
            model=self.model,
            provider=self.name,
        )

    def _judge(self, system: str, messages: list[dict]) -> LLMResponse:
        """Deterministic valid-JSON judge output (hash-derived score) — hermetic, non-constant."""
        from src.utils.hashing import sha256_hex

        h = sha256_hex({"s": system, "m": messages})
        # Range chosen so a well-behaved run clears the Foundational gate deterministically.
        score = round(0.75 + 0.2 * (int(h[:4], 16) / 0xFFFF), 3)  # [0.75, 0.95]
        s = system.lower()
        if "customer experience" in s:
            payload = {
                "cx_score": score,
                "reasoning": "stub judge (deterministic)",
                "notable_turns": [],
            }
        elif "belief system" in s or "breath" in s:
            payload = {
                "coherence_score": score,
                "reasoning": "stub judge (deterministic)",
                "violations": [],
            }
        else:  # SOUL / emotional stability
            payload = {
                "stability_score": score,
                "reasoning": "stub judge (deterministic)",
                "concerns": [],
            }
        content = json.dumps(payload)
        return LLMResponse(
            content=content,
            tokens_input=len(system) // 4,
            tokens_output=len(content) // 4,
            model=self.model,
            provider=self.name,
        )

    async def health_check(self) -> dict:
        return {"provider": "stub", "ok": True}


# ═══════════════════════════════════════════════════════════════
# Retry helper for real providers
# ═══════════════════════════════════════════════════════════════


async def _with_retries(fn, *, max_retries: int, retry_on):
    delay = 1.0
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except retry_on as exc:  # network / 5xx
            last_exc = exc
            if attempt == max_retries:
                break
            await asyncio.sleep(delay)
            delay *= 2
    raise last_exc  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════
# OllamaProvider
# ═══════════════════════════════════════════════════════════════


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float = 60.0, max_retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs,
    ) -> LLMResponse:
        import httpx

        payload = {
            "model": self.model,
            "messages": to_chat_messages(system, messages),
            "stream": False,
            "options": {
                "seed": int(kwargs.get("seed", 0)),
                "temperature": temperature,
                "top_p": 1.0,
                "num_predict": max_tokens,
            },
        }
        started = time.perf_counter()

        async def _call() -> dict:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError("5xx", request=resp.request, response=resp)
                resp.raise_for_status()
                return resp.json()

        data = await _with_retries(
            _call,
            max_retries=self.max_retries,
            retry_on=(httpx.TransportError, httpx.HTTPStatusError),
        )
        content = (data.get("message") or {}).get("content", "").strip()
        return LLMResponse(
            content=content,
            tokens_input=int(data.get("prompt_eval_count", 0)),
            tokens_output=int(data.get("eval_count", 0)),
            model=self.model,
            provider=self.name,
            finish_reason=data.get("done_reason", "stop"),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    async def health_check(self) -> dict:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                return {"provider": "ollama", "ok": r.status_code == 200}
        except Exception:  # noqa: BLE001
            return {"provider": "ollama", "ok": False}


# ═══════════════════════════════════════════════════════════════
# AnthropicProvider
# ═══════════════════════════════════════════════════════════════


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout: float = 60.0, max_retries: int = 3):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs,
    ) -> LLMResponse:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self.api_key, timeout=self.timeout)
        chat = [
            {
                "role": "assistant" if m.get("role") == "agent" else "user",
                "content": m.get("content", ""),
            }
            for m in messages
        ] or [{"role": "user", "content": "Begin."}]
        started = time.perf_counter()

        async def _call():
            return await client.messages.create(
                model=self.model,
                system=system,
                messages=chat,
                temperature=temperature,
                top_p=1.0,
                max_tokens=max_tokens,
            )

        # Retry on 5xx / connection; never retry 4xx (bad request / auth).
        msg = await _with_retries(
            _call,
            max_retries=self.max_retries,
            retry_on=(anthropic.APIConnectionError, anthropic.InternalServerError),
        )
        content = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return LLMResponse(
            content=content.strip(),
            tokens_input=msg.usage.input_tokens,
            tokens_output=msg.usage.output_tokens,
            model=self.model,
            provider=self.name,
            finish_reason=msg.stop_reason or "stop",
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    async def health_check(self) -> dict:
        return {"provider": "anthropic", "ok": bool(self.api_key)}


# ═══════════════════════════════════════════════════════════════
# CachedLLMProvider — wraps any provider with the hermetic cache
# ═══════════════════════════════════════════════════════════════

_JUDGE_KEYS = {
    "content",
    "tokens_input",
    "tokens_output",
    "model",
    "provider",
    "finish_reason",
    "latency_ms",
}


class CachedLLMProvider(LLMProvider):
    def __init__(self, inner: LLMProvider, cache: LLMResponseCache, purpose: str = "agent"):
        self.inner = inner
        self.cache = cache
        self.purpose = purpose
        self.name = inner.name
        self.model = inner.model

    def _request(self, system, messages, temperature, max_tokens, seed) -> dict:
        return {
            "provider": self.inner.name,
            "model": self.inner.model,
            "system": system,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "seed": seed,
            "purpose": self.purpose,
        }

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs,
    ) -> LLMResponse:
        seed = int(kwargs.get("seed", 0))
        request = self._request(system, messages, temperature, max_tokens, seed)
        key = self.cache.key_for(request)
        cached = await self.cache.get(key)
        if cached is not None:
            resp = LLMResponse(**{k: v for k, v in cached.items() if k in _JUDGE_KEYS}, cached=True)
            _emit_tokens(resp, self.purpose)
            return resp

        inner_kwargs = {k: v for k, v in kwargs.items() if k != "purpose"}
        resp = await self.inner.complete(
            system=system,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            purpose=self.purpose,
            **inner_kwargs,
        )
        await self.cache.put(
            request,
            {k: v for k, v in asdict(resp).items() if k in _JUDGE_KEYS},
            provider=resp.provider,
            model=resp.model,
        )
        _emit_tokens(resp, self.purpose)
        log.info(
            "llm_call",
            provider=resp.provider,
            model=resp.model,
            purpose=self.purpose,
            tokens=resp.tokens,
            latency_ms=resp.latency_ms,
            cached=False,
            run_id=kwargs.get("run_id"),
        )
        return resp

    async def health_check(self) -> dict:
        return await self.inner.health_check()


# ═══════════════════════════════════════════════════════════════
# Factories
# ═══════════════════════════════════════════════════════════════


# Reachability probe for `auto` mode. Cached per-process so we probe at most once per base_url —
# never in the hot path of every judge call. A short timeout keeps a down Ollama from stalling.
_reachable_cache: dict[str, bool] = {}


def _ollama_reachable(base_url: str, *, timeout: float = 1.5) -> bool:
    """True if an Ollama server answers at base_url (GET /api/tags 200). Cached per base_url."""
    if base_url in _reachable_cache:
        return _reachable_cache[base_url]
    ok = False
    try:
        import urllib.request

        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=timeout) as r:
            ok = r.status == 200
    except Exception:  # noqa: BLE001 — any error (down, refused, timeout) = not reachable
        ok = False
    _reachable_cache[base_url] = ok
    return ok


def reset_reachability_cache() -> None:
    """Clear the cached probe result (tests that flip reachability)."""
    _reachable_cache.clear()


def resolve_provider(provider: str) -> str:
    """Resolve a provider name, expanding `auto` → ollama-if-reachable-else-stub (ADR-0023).

    `auto` is the setting to use for real-signal runs: it prefers the live Ollama judge when
    `OLLAMA_BASE_URL` answers, and falls back to the deterministic StubProvider otherwise — so the
    same config is safe in CI (Ollama unreachable → stub → hermetic) and locally (Ollama up → real).
    """
    if provider == "auto":
        return "ollama" if _ollama_reachable(settings.ollama_base_url) else "stub"
    return provider


def _concrete(provider: str, *, agent_model: str, judge_model: str, is_judge: bool) -> LLMProvider:
    model = judge_model if is_judge else agent_model
    if provider == "ollama":
        return OllamaProvider(
            settings.ollama_base_url,
            model,
            settings.llm_request_timeout_seconds,
            settings.llm_max_retries,
        )
    if provider == "anthropic":
        return AnthropicProvider(
            settings.anthropic_api_key or "",
            model,
            settings.llm_request_timeout_seconds,
            settings.llm_max_retries,
        )
    return StubProvider()


def get_agent_llm() -> LLMProvider:
    provider = resolve_provider(settings.llm_provider)
    agent_model = (
        settings.ollama_agent_model if provider == "ollama" else settings.anthropic_agent_model
    )
    inner = _concrete(provider, agent_model=agent_model, judge_model="", is_judge=False)
    return CachedLLMProvider(inner, LLMResponseCache(), purpose="agent")


def get_judge_llm() -> LLMProvider:
    provider = resolve_provider(settings.llm_judge_provider)
    judge_model = (
        settings.ollama_judge_model if provider == "ollama" else settings.anthropic_judge_model
    )
    inner = _concrete(provider, agent_model="", judge_model=judge_model, is_judge=True)
    return CachedLLMProvider(inner, LLMResponseCache(), purpose="judge")


# Backward-compatible alias (used by the runner default + scripts).
def get_llm_provider() -> LLMProvider:
    return get_agent_llm()
