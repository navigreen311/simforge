"""Web-search ingestion provider (Batch 5, ADR-0042).

Finds real-world sources for a query and returns extraction-ready text. This module ONLY fetches
candidate source text — it does not create scenarios. The returned text feeds the exact same
`extract_scenario` → human-review → commit path as paste/document ingestion, so the cardinal rule
still holds: a web result becomes an AI-drafted DRAFT that a human must approve and commit.

Provider seam (mirrors the LLM provider pattern):
  * TavilyProvider — live search-and-extract via the Tavily API (returns cleaned page content).
  * StubWebSearchProvider — no key configured → raises WebSearchUnavailable (honest "not
    configured"). This is the default in dev/CI, so there is no network dependency and no fake
    results are ever fabricated.
Resolution: WEB_SEARCH_PROVIDER=auto → tavily-if-TAVILY_API_KEY-set-else-stub.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.config import settings

# Cap per-result text so it fits the extraction single-pass budget (12k chars) with headroom.
_MAX_RESULT_CHARS = 10_000


class WebSearchUnavailable(Exception):
    """Web search was requested but no provider is configured (no fabrication, no fallback)."""


@dataclass
class WebSearchResult:
    title: str
    url: str
    content: str  # extraction-ready text (already truncated)
    snippet: str  # short description for the results list
    score: float | None = None
    published_date: str | None = None


class WebSearchProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    async def search(self, query: str, max_results: int) -> list[WebSearchResult]: ...


def _parse_tavily(data: dict) -> list[WebSearchResult]:
    """Map a Tavily /search response into WebSearchResults. Prefers full page text over snippet."""
    out: list[WebSearchResult] = []
    for r in data.get("results", []):
        if not isinstance(r, dict):
            continue
        url = (r.get("url") or "").strip()
        if not url:
            continue
        snippet = (r.get("content") or "").strip()
        # raw_content is the full cleaned page text (present when include_raw_content=true).
        body = (r.get("raw_content") or r.get("content") or "").strip()
        score = r.get("score")
        out.append(
            WebSearchResult(
                title=(r.get("title") or url).strip(),
                url=url,
                content=body[:_MAX_RESULT_CHARS],
                snippet=snippet[:400],
                score=float(score) if isinstance(score, (int, float)) else None,
                published_date=r.get("published_date"),
            )
        )
    return out


class TavilyProvider(WebSearchProvider):
    name = "tavily"

    def __init__(self, api_key: str, api_url: str, timeout: float):
        self.api_key = api_key
        self.api_url = api_url
        self.timeout = timeout

    async def search(self, query: str, max_results: int) -> list[WebSearchResult]:
        import httpx

        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_raw_content": True,
            "include_answer": False,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.api_url, json=payload)
            resp.raise_for_status()
            return _parse_tavily(resp.json())


class StubWebSearchProvider(WebSearchProvider):
    name = "stub"

    async def search(self, query: str, max_results: int) -> list[WebSearchResult]:
        raise WebSearchUnavailable(
            "Web search is not configured. Set WEB_SEARCH_PROVIDER=tavily and TAVILY_API_KEY to "
            "enable live web ingestion. No results are fabricated."
        )


def resolve_web_search_provider(provider: str) -> str:
    """Expand `auto` → tavily-if-key-else-stub (mirrors the LLM auto resolution)."""
    if provider == "auto":
        return "tavily" if settings.tavily_api_key else "stub"
    return provider


def web_search_available() -> bool:
    """True only when a real provider is fully configured (used to gate the UI honestly)."""
    return resolve_web_search_provider(settings.web_search_provider) == "tavily" and bool(
        settings.tavily_api_key
    )


def get_web_search_provider() -> WebSearchProvider:
    resolved = resolve_web_search_provider(settings.web_search_provider)
    if resolved == "tavily" and settings.tavily_api_key:
        return TavilyProvider(
            settings.tavily_api_key,
            settings.tavily_api_url,
            settings.web_search_timeout_seconds,
        )
    return StubWebSearchProvider()


async def search_web(query: str, max_results: int | None = None) -> list[WebSearchResult]:
    """Search for candidate sources. Raises WebSearchUnavailable if no provider is configured."""
    provider = get_web_search_provider()
    n = max_results or settings.web_search_max_results
    return await provider.search(query.strip(), n)
