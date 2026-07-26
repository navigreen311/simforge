# ADR-0042 — Web-search ingestion for the Scenario Bank

**Status:** Accepted (2026-07-26).

## Context
The Scenario Bank (ADR pending / PRs #56, #57) ingests scenarios from manual authoring, pasted text,
and uploaded documents. Batch 5 of the spec calls for **web-search ingestion**: find real-world
sources for a query, pull their text, and turn a chosen source into a scenario candidate. Two hard
constraints from the Scenario Bank cardinal rule apply unchanged:

1. **Nothing auto-commits.** A web result must land as an AI-drafted DRAFT that a human reviews and
   separately commits — identical to paste/document ingestion.
2. **No fabrication.** If no provider is configured (or a search returns nothing), the system says so
   and produces no scenario. It never invents a source or a result to fill the gap.

The stack had no web-search capability, so the Web tab previously shipped as an honest "pending
dependency" stub (Batch 4 gate G1).

## Decision
- **Provider seam, mirroring the LLM provider pattern.** `services/scenario_bank/web_search.py`
  defines a `WebSearchProvider` ABC with two implementations: `TavilyProvider` (live) and
  `StubWebSearchProvider` (raises `WebSearchUnavailable`). `WEB_SEARCH_PROVIDER=auto` resolves to
  `tavily`-if-`TAVILY_API_KEY`-set-else-`stub` — the same `auto` semantics as the LLM providers, so
  the default (no key) is a hermetic stub with no network dependency and CI stays offline.
- **Tavily is the chosen provider.** It is purpose-built for LLM ingestion: a single `/search` call
  returns cleaned, extraction-ready page text (`raw_content`), collapsing search + fetch + HTML-strip
  into one request. Generous free tier, independent index, simple REST. The seam keeps any other
  provider (Brave, SerpAPI, Exa) a drop-in addition.
- **Maximal reuse of the existing extraction path.** Web search only *fetches text*. Each result's
  `content` is fed to the **existing** `POST /extract` with `source_type="web"`, `source_ref=<url>`,
  so extraction, the human review form, the two-stage promotion, and the `derived_from` Lineage
  provenance edge all work with no new code. Per-result text is truncated to 10k chars to fit the
  extraction single-pass budget.
- **Honest availability surface.** `GET /web-search/status` and the `available` field on
  `POST /web-search` tell the UI whether a real provider is configured. When it is not, the Web tab
  renders the same "not configured — no results fabricated" empty state; when it is, it shows a
  search box → results list → "Use this source" → the standard review-then-save-draft flow.

## Consequences
- Activation is a one-step env flip: set `WEB_SEARCH_PROVIDER=tavily` and `TAVILY_API_KEY=tvly-…`.
  No code change, no migration. The stub default means dev/CI behavior is unchanged and hermetic.
- The Tavily HTTP call itself is exercised by a hermetic response-parsing unit test; a real network
  round-trip requires a provisioned key (a human step), like every other external provider in the
  platform (Clerk, HSM, Linear, real Forges).
- Cost is bounded by the provider's own quota; no SimForge budget cap is wired to search yet (search
  is not run cost — it is ingestion tooling). If needed, a cap can be added later.
- Video/YouTube (Batch 6) remains a stub pending transcription (gate G2/G3), unchanged.
