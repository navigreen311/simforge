"""OpenTelemetry distributed tracing (blueprint §H.3; ADR-0031).

No-op unless activated. When ``OTEL_TRACES_ENABLED`` or ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set, a
``TracerProvider`` (resource ``service.name=simforge-api``) is installed; with an endpoint, spans
export via OTLP/HTTP to a collector (Grafana Tempo in the reference stack, ``infra/compose``).
FastAPI requests are auto-instrumented; services add manual spans with :func:`span`.

Design goal: ``span(...)`` is always safe to call. When tracing is off, OpenTelemetry's default
proxy provider yields a no-op tracer — zero cost, no collector, hermetic CI. So call sites never
branch on whether tracing is enabled.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from opentelemetry import trace

if TYPE_CHECKING:
    from fastapi import FastAPI
    from opentelemetry.trace import Span, Tracer

_CONFIGURED = False


def tracing_enabled() -> bool:
    from src.config import settings

    return settings.otel_traces_enabled or bool(settings.otel_exporter_otlp_endpoint)


def configure_tracing() -> None:
    """Install the global TracerProvider + OTLP exporter (idempotent). No-op when disabled."""
    global _CONFIGURED
    if _CONFIGURED or not tracing_enabled():
        return

    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

    from src.config import settings

    resource = Resource.create(
        {"service.name": settings.otel_service_name, "service.version": settings.app_version}
    )
    provider = TracerProvider(
        resource=resource,
        sampler=ParentBased(TraceIdRatioBased(settings.otel_sample_ratio)),
    )

    endpoint = settings.otel_exporter_otlp_endpoint.strip()
    if endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        # OTLP/HTTP wants the signal-specific path; accept either a base URL or a full /v1/traces.
        url = endpoint if endpoint.endswith("/v1/traces") else endpoint.rstrip("/") + "/v1/traces"
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=url)))

    trace.set_tracer_provider(provider)
    _CONFIGURED = True


def instrument_app(app: FastAPI) -> None:
    """Auto-instrument FastAPI request handling (one server span per request). No-op when off."""
    if not tracing_enabled():
        return
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)


def get_tracer() -> Tracer:
    return trace.get_tracer("simforge")


@contextlib.contextmanager
def span(name: str, **attributes: Any) -> Iterator[Span]:
    """Start a child span. Cheap no-op when tracing is disabled; safe to wrap any operation."""
    with get_tracer().start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, value)
        yield current
