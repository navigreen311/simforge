"""OTEL tracing (ADR-0031) — hermetic: no collector, no network.

Verifies (1) `span()` is a safe no-op when tracing is disabled, (2) with an in-memory provider
installed it emits a named span carrying its attributes, and (3) the enabled/disabled predicate +
config exposure behave as documented.
"""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from src.config import settings
from src.telemetry import tracing


def test_span_is_noop_when_disabled() -> None:
    """With no SDK provider installed, span() must not raise — call sites never branch."""
    with tracing.span("noop.op", **{"x.y": 1}) as s:
        s.set_attribute("added", True)
    # No provider → no spans recorded anywhere; the point is simply that this did not raise.


@pytest.fixture
def in_memory_spans() -> InMemorySpanExporter:
    """Install a real SDK provider with an in-memory exporter for the duration of the test."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    # Force-install even if a prior test set the global (OTEL blocks silent override otherwise).
    trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]
    trace.set_tracer_provider(provider)
    yield exporter
    trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]


def test_span_emits_with_attributes(in_memory_spans: InMemorySpanExporter) -> None:
    with tracing.span("scenario.run", **{"scenario.id": "scn.gs.src.001", "skip": None}):
        pass
    spans = in_memory_spans.get_finished_spans()
    assert [s.name for s in spans] == ["scenario.run"]
    attrs = dict(spans[0].attributes or {})
    assert attrs["scenario.id"] == "scn.gs.src.001"
    assert "skip" not in attrs  # None-valued attributes are dropped


def test_tracing_enabled_predicate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "otel_traces_enabled", False)
    monkeypatch.setattr(settings, "otel_exporter_otlp_endpoint", "")
    assert tracing.tracing_enabled() is False

    monkeypatch.setattr(settings, "otel_traces_enabled", True)
    assert tracing.tracing_enabled() is True

    monkeypatch.setattr(settings, "otel_traces_enabled", False)
    monkeypatch.setattr(settings, "otel_exporter_otlp_endpoint", "http://tempo:4318")
    assert tracing.tracing_enabled() is True


@pytest.mark.asyncio
async def test_health_config_reports_tracing(client) -> None:  # noqa: ANN001
    resp = await client.get("/api/health/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["tracing_enabled"] is False  # default off keeps CI hermetic
    assert body["tracing_exporter"] is False
