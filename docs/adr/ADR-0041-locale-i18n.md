# ADR-0041 — Locale / i18n layer

**Status:** Accepted (2026-07-21).

## Context
SimForge was English/Nevada-only. The blueprint's v1.2 "locale Packs" — multi-language support — had
no implementation. The highest-leverage, bounded slice of i18n is the platform's **own** generated
language: the LLM-judge rubric prompts (P7 customer-experience, C1 breath-coherence, C2 soul-stability).
Scenario *content* is pack-author text (a different concern); the rubric prompts are SimForge's, so
localizing them is what makes the certifier speak a venture's language.

## Decision
- **A pack declares its locale.** `PackSpec.locale` (default `en`, validated against `LOCALES =
  ("en", "es")`) flows through ingestion → `Pack.locale` → `EvalContext.locale` → the judge scorers.
- **Locale-aware prompt resolution.** `render_prompt(name, locale=...)` prefers `{name}.{locale}.txt`
  and falls back to the English base `{name}.txt`. **English uses the base file (no `en` suffix)**, so
  the default path — and therefore every existing pack's scores — is byte-for-byte unchanged. Shipped
  Spanish translations for all three judge prompts, with identical `$variables` and JSON schema keys
  (only the prose is translated, so parsing is untouched).
- **Registry surface.** `GET /api/locales` reports the supported locales and per-prompt coverage;
  `Pack.locale` is exposed in the pack API and shown as a badge in the dashboard.

## Consequences
- **Zero regression risk for existing packs:** they default to `en` → base prompts → identical judge
  scores. The Golden Benchmark (ADR-0033) stays green, confirming this end-to-end.
- A pack in another locale gets translated rubric prompts, and — because the judge input changes — its
  P7/C1/C2 scores are computed against that language (verified: the same run scores differently under
  `es` vs `en`). Unknown locales fall back to English rather than failing.
- Extending to a new language is additive: drop `{name}.{locale}.txt` files, add the code to
  `LOCALES`, and packs can declare it — no scorer or schema change.
- Scope is honest: this localizes the **rubric-judge layer**, not pack-authored scenario content
  (which a pack author writes in their own language already). The seam (`EvalContext.locale`) is where
  broader localization would hang.

## Cross-references
Blueprint §L.4 (locale Packs). `PackSpec.locale`, `src/services/evaluation/prompts/`, ADR-0008 (the
judge prompts localized here), ADR-0033 (golden baseline that proves `en` is unchanged).
