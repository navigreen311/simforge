"""LLM provider abstraction (blueprint §C.8).

Dev default is a deterministic, offline **StubProvider** (same philosophy as StubSigner —
ADR-0001): reproducible, free, no network. Ollama/OpenAI providers drop in behind the same
interface without touching call sites.
"""

from __future__ import annotations

import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

_NAME_RE = re.compile(r"You are ([^,]+),")


@dataclass
class LLMResponse:
    content: str
    tokens: int


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, *, system: str, messages: list[dict], seed: int) -> LLMResponse: ...


class StubProvider(LLMProvider):
    """Deterministic in-character responder for dev/test. No external calls."""

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

    async def complete(self, *, system: str, messages: list[dict], seed: int) -> LLMResponse:
        turn = len(messages)
        rng = random.Random((seed << 8) ^ turn)
        name_match = _NAME_RE.search(system)
        name = name_match.group(1).strip() if name_match else "The agent"

        last = messages[-1]["content"] if messages else ""
        # Reference a short snippet of the latest input to feel grounded.
        snippet = " ".join(last.split()[:8])

        parts = [rng.choice(self._OPENERS)]
        if snippet:
            parts.append(f'Regarding "{snippet}…", {rng.choice(self._MOVES).lower()}')
        else:
            parts.append(rng.choice(self._MOVES))
        # Signal resolution intent as turns progress (used by the runner heuristic).
        # Threshold chosen so a mid-run complication lands before resolution.
        if turn >= 5:
            parts.append("I think we've reached a workable resolution.")
        parts.append(rng.choice(self._CLOSERS))

        content = f"{name}: " + " ".join(parts)
        tokens = max(1, int(len(content.split()) * 1.3))
        return LLMResponse(content=content, tokens=tokens)


def to_ollama_messages(system: str, messages: list[dict]) -> list[dict]:
    """Map SimForge transcript turns → Ollama chat roles.

    The transcript uses scenario/agent/world roles; Ollama expects system/user/assistant.
    The tested agent is the assistant; the scenario + mock world are the user.
    """
    out: list[dict] = [{"role": "system", "content": system}]
    for m in messages:
        role = "assistant" if m.get("role") == "agent" else "user"
        out.append({"role": role, "content": m.get("content", "")})
    return out


class OllamaProvider(LLMProvider):
    """Local Ollama chat completion (blueprint default for Village routes)."""

    def __init__(self, base_url: str, model: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def complete(self, *, system: str, messages: list[dict], seed: int) -> LLMResponse:
        import httpx

        payload = {
            "model": self.model,
            "messages": to_ollama_messages(system, messages),
            "stream": False,
            "options": {"seed": seed, "temperature": 0.7},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        content = (data.get("message") or {}).get("content", "").strip()
        tokens = int(data.get("prompt_eval_count", 0)) + int(data.get("eval_count", 0))
        if tokens <= 0:
            tokens = max(1, int(len(content.split()) * 1.3))
        return LLMResponse(content=content, tokens=tokens)


class OpenAIProvider(LLMProvider):
    """OpenAI fallback. WEEK: real client using OPENAI_API_KEY (Anthropic also viable)."""

    async def complete(self, *, system: str, messages: list[dict], seed: int) -> LLMResponse:
        raise NotImplementedError("OpenAIProvider not enabled in this environment")


def _ollama_reachable(base_url: str, timeout: float = 1.0) -> bool:
    import socket
    from urllib.parse import urlparse

    parsed = urlparse(base_url)
    host, port = parsed.hostname or "localhost", parsed.port or 11434
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def get_llm_provider() -> LLMProvider:
    """Select the agent-runtime LLM provider from settings.

    - "stub"   → deterministic offline StubProvider (default; keeps tests reproducible)
    - "ollama" → local Ollama (settings.ollama_model)
    - "auto"   → Ollama if reachable, else StubProvider
    - "openai" → OpenAIProvider (not enabled in this environment)
    """
    from src.config import settings

    provider = settings.llm_provider.lower()
    if provider == "ollama":
        return OllamaProvider(
            settings.ollama_base_url, settings.ollama_model, settings.llm_timeout_seconds
        )
    if provider == "auto":
        if _ollama_reachable(settings.ollama_base_url):
            return OllamaProvider(
                settings.ollama_base_url, settings.ollama_model, settings.llm_timeout_seconds
            )
        return StubProvider()
    if provider == "openai":
        return OpenAIProvider()
    return StubProvider()
