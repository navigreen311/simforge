# Grafana — SimForge governance dashboard (ADR-0029)

SimForge exposes Prometheus metrics at `GET /metrics` (blueprint §H.2). This directory ships the
Grafana wiring as-code so a deployment gets the dashboard with zero click-ops.

## Files
- `infra/grafana/provisioning/datasources/prometheus.yaml` — the Prometheus datasource (`PROMETHEUS_URL`, default `http://prometheus:9090`).
- `infra/grafana/provisioning/dashboards/dashboards.yaml` — loads dashboards from `/var/lib/grafana/dashboards`.
- `infra/grafana/dashboards/simforge-overview.json` — the **Governance Overview** dashboard.

## Panels (all backed by real emitted metrics)
- Scenario runs by status · readiness-gate outcomes · certs issued · open gaps
- **PDP**: decisions by decision, decision latency p95, cache-hit ratio (ADR-0024)
- Eval latency p95 · LLM tokens by provider

## Run it (docker-compose in `infra/compose/`, ADR-0030)
```bash
cd infra/compose
docker compose up -d prometheus grafana
# Grafana → http://localhost:3001 (admin/admin), the SimForge folder is pre-provisioned.
```
Grafana mounts `infra/grafana/provisioning` → `/etc/grafana/provisioning` and
`infra/grafana/dashboards` → `/var/lib/grafana/dashboards`; Prometheus scrapes the API's `/metrics`.

## Adding a panel
Edit `simforge-overview.json` (or regenerate it) — target `expr`s must reference metric names the
API actually emits (`src/telemetry/metrics.py`); a test (`test_grafana_dashboard.py`) checks the
dashboard is valid JSON and references the core metrics, so a rename is caught in CI.
