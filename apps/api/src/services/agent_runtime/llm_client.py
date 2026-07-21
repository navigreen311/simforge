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


class OllamaProvider(LLMProvider):
    """Local Ollama (blueprint default for Village routes). WEEK 4+: httpx to OLLAMA_BASE_URL."""

    async def complete(self, *, system: str, messages: list[dict], seed: int) -> LLMResponse:
        raise NotImplementedError("OllamaProvider not enabled in this environment")


class OpenAIProvider(LLMProvider):
    """OpenAI fallback. WEEK 4+: real client using OPENAI_API_KEY."""

    async def complete(self, *, system: str, messages: list[dict], seed: int) -> LLMResponse:
        raise NotImplementedError("OpenAIProvider not enabled in this environment")


def get_llm_provider() -> LLMProvider:
    """Select a provider. Dev with no real LLM configured → deterministic StubProvider.

    WEEK 4+: return Ollama (settings.ollama_base_url) / OpenAI when reachable/configured.
    """
    return StubProvider()
