# ADR-0029 — Real Linear gap-ticketing + Grafana dashboards

**Status:** Accepted (2026-07-21).

## Context
Two observability/routing seams were still stubs: the Linear client (gap tickets) raised
`NotImplementedError`, and although the API exposes real Prometheus metrics (`/metrics`, §H.2), there
was no Grafana wiring to see them. Neither a live Linear workspace nor a running Grafana is available
here, so the goal is **deployable, tested code + as-code dashboards** that activate on config —
matching the Clerk/HSM/Forge-HTTP pattern (real path, injectable transport, hermetic tests).

## Decision
### Linear (`services/reporter/linear_client.py`)
- Real `issueCreate` GraphQL mutation against `LINEAR_API_URL` (default the Linear API), authorized
  with `LINEAR_API_KEY`, into `LINEAR_TEAM_ID`. Title is namespaced `[project] title`; metadata is
  folded into the issue body; returns the created issue id + url.
- **No-op by default** — empty key/team → returns an empty ticket, nothing posted (dev unchanged).
- **Best-effort** — any HTTP/GraphQL error is logged and returns an empty ticket; a Linear outage
  never blocks gap emission.
- Injectable `httpx` transport → the real path is hermetically tested (success, unsuccessful,
  transport-error) with no network.

### Grafana (`infra/grafana/`)
- **Dashboards as-code** — `dashboards/simforge-overview.json` (a "Governance Overview" with 10
  panels) + provisioning for the Prometheus datasource and the dashboard loader. All panel `expr`s
  reference metrics the API actually emits (runs, gate, certs, gaps, **PDP** decisions/latency/
  cache-hit, eval latency, tokens).
- A test (`test_grafana_dashboard.py`) asserts the dashboard is valid JSON, has ≥8 panels, and that
  every core metric it charts is registered in `src/telemetry/metrics.py` — so a metric rename is
  caught in CI, not in production.

## Consequences
- Gap tickets and dashboards are one config away: set `LINEAR_API_KEY`/`LINEAR_TEAM_ID` and point
  Grafana at `infra/grafana/provisioning` (the compose stack in ADR-0030 does this). No code change.
- What can/can't be verified here: the Linear GraphQL request/response handling and no-op/best-effort
  behavior are unit-tested against a mock transport; the dashboard is JSON-valid and metric-checked.
  The live round-trip to a real Linear workspace and the Grafana render need those external systems
  and happen at deploy time — the untested surface is the network hop, not the logic.

## Cross-references
Blueprint §C.11 (gap routing to Linear), §H.2 (metrics), ADR-0018/0016 (the injectable-transport +
config-gated pattern), ADR-0024 (PDP metrics the dashboard charts), ADR-0030 (deploy compose that
wires Prometheus + Grafana).
