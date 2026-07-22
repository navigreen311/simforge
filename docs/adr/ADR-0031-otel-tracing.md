# ADR-0031 — OpenTelemetry distributed tracing → Tempo

**Status:** Accepted (2026-07-21).

## Context
Observability had two of its three pillars real: Prometheus metrics (`/metrics`) and structured
JSON logs (structlog). The third — **distributed traces** — was a `WEEK 9` stub: `configure_tracing()`
returned `None`. Without spans, there's no per-request/per-run latency breakdown and no way to see
where a slow certification run actually spends its time (agent turns vs. Forge side-effects vs.
eval). The blueprint (§H.3) specifies OTEL traces exported to Grafana Tempo. The constraint, as with
every external seam: CI must stay hermetic (no collector, no network) and tracing must cost nothing
when off.

## Decision
- **Config-gated seam.** Tracing is a no-op unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set (export to a
  collector) or `OTEL_TRACES_ENABLED=true` (build spans locally without exporting). Default off.
- **`span(name, **attrs)` is always safe to call.** When tracing is disabled, OpenTelemetry's default
  proxy provider returns a no-op tracer — zero cost. So service code (`run_scenario`, PDP `decide`)
  wraps hot paths in `span(...)` **unconditionally**, never branching on whether tracing is on.
- **What's instrumented.** FastAPI request handling is auto-instrumented (`FastAPIInstrumentor`, one
  server span per request); `scenario.run` wraps the agent-execution path (attrs: scenario id, tier,
  agent, execution mode); `pdp.decide` wraps the authorization hot path (attrs: subject, action,
  decision, reason). Spans nest under the request span, so a trace shows request → run → decision.
- **Export.** `TracerProvider` (resource `service.name=simforge-api`) with a `ParentBased(TraceIdRatioBased)`
  sampler (`OTEL_SAMPLE_RATIO`, default 1.0) and a `BatchSpanProcessor` → OTLP/HTTP exporter to
  `${OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces`.
- **Reference stack.** `infra/compose` adds a single-binary **Tempo** service (OTLP/HTTP on :4318,
  query on :3200) + a Grafana Tempo datasource (`infra/grafana/provisioning/datasources/tempo.yaml`,
  with trace→metrics correlation to the existing Prometheus datasource). The API service points
  `OTEL_EXPORTER_OTLP_ENDPOINT` at `http://tempo:4318`.
- **Deploy-readiness.** `GET /api/health/config` now reports `tracing_enabled` + `tracing_exporter`
  (modes only, no secrets), so an operator can confirm traces are actually flowing.

## Consequences
- Traces flow end-to-end in the compose stack; in CI and default local runs, spans compile to the
  no-op tracer — hermetic, no collector dependency, no measurable overhead.
- New runtime deps (`opentelemetry-sdk`, `-exporter-otlp-proto-http`, `-instrumentation-fastapi`).
  The OTLP exporter is imported lazily inside `configure_tracing()` only when an endpoint is set.
- Verified: unit tests assert `span()` is a safe no-op when disabled and emits a correctly-named,
  correctly-attributed span through an in-memory exporter when enabled; the app boots with tracing
  enabled (provider installed, FastAPI instrumented) with no collector present.
- What needs real infra at deploy time: pointing at a live Tempo/OTLP collector and viewing traces
  in Grafana. The wiring, exporter, and stack service are complete and validated here.

## Cross-references
Blueprint §H.3 (tracing), §H.2 (metrics correlation). `src/telemetry/tracing.py`,
`infra/compose/{docker-compose.full.yml,tempo.yaml}`, `docs/deploy.md` (observability).
