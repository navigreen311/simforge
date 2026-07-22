# ADR-0039 — Monthly cost-cap enforcement

**Status:** Accepted (2026-07-21).

## Context
The blueprint specifies monthly budget ceilings — a sandbox cap and a v1.2 integrated-run cap
(default $500) — and `simforge_budget_sandbox_monthly_usd` had existed as a *setting* with nothing
enforcing it. Every run already records a metered `costUsd` (0 for the free stub/local providers,
non-zero once a real LLM or Forge sandbox is active). A runaway real-provider spend should be stopped
before it happens, not discovered on the invoice.

## Decision
- **`enforce_budget(session, mode)`** sums the current **calendar month's** `costUsd` for that
  execution mode and raises `BudgetExceededError` when spend has reached the cap. Called inside
  `run_scenario` **immediately after the sandbox/integrated mode is resolved and before any billable
  work** — so a blocked run does no LLM/Forge calls and creates no Run row.
- **Separate caps per mode** — `SIMFORGE_BUDGET_SANDBOX_MONTHLY_USD` (default $50) and
  `SIMFORGE_BUDGET_INTEGRATED_MONTHLY_USD` (default $500); the run's actual mode selects which.
- **Surface:** the run endpoint maps `BudgetExceededError` → `402 Payment Required` with a
  human-readable detail; `GET /api/budget/status` reports spend / cap / remaining / exceeded for both
  modes this month.

## Consequences
- Hermetic by construction: stub/local providers cost 0, so the cap never trips in dev/CI and no
  existing test changes behaviour. It binds only once a real metered provider is active — exactly
  where it's needed.
- Enforcement is pre-flight (before the Run row + before billable work), so an over-budget month
  fails fast and cheap.
- The window is the calendar month (`startedAt >= month_start`), matching how the cap is expressed;
  a new month resets spend automatically with no job.
- Verified: status starts empty; a stub run proceeds under the default cap; with the cap forced to 0
  and a recorded non-zero cost, `status.exceeded` is true and the next run returns 402.

## Cross-references
Blueprint §H (budget), §L.4 (v1.2 integrated cap). `src/services/budget/`, ADR-0025 (integrated runs —
the mode with its own cap), the `simforge_tokens_used_total` / cost metrics.
