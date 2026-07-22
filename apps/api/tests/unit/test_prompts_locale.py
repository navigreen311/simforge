"""Locale-aware rubric prompts (ADR-0041)."""

from __future__ import annotations

import pytest

from src.services.evaluation.prompts import available_locales, render_prompt


def test_available_locales_includes_base_and_translations() -> None:
    assert available_locales("p7_cx") == ["en", "es"]
    assert available_locales("c1_breath") == ["en", "es"]
    assert available_locales("c2_soul") == ["en", "es"]


def test_render_spanish_uses_translated_template() -> None:
    es = render_prompt("p7_cx", locale="es", persona_json="{}", scenario_title="x")
    assert "Responde SOLO con JSON" in es
    assert "cx_score" in es  # the schema key stays identical for parsing


def test_render_english_uses_base_template() -> None:
    en = render_prompt("p7_cx", locale="en", persona_json="{}", scenario_title="x")
    assert "Respond ONLY with valid JSON" in en
    assert "Responde SOLO" not in en


def test_unknown_locale_falls_back_to_english() -> None:
    fr = render_prompt("p7_cx", locale="fr", persona_json="{}", scenario_title="x")
    en = render_prompt("p7_cx", locale="en", persona_json="{}", scenario_title="x")
    assert fr == en  # no fr template → English base


@pytest.mark.asyncio
async def test_locale_flows_through_the_judge_scorer() -> None:
    """A different locale changes the judge prompt, so the (deterministic stub) score differs."""
    from src.services.agent_runtime.llm_client import StubProvider
    from src.services.evaluation.dimensions import p7_cx
    from src.services.evaluation.types import EvalContext

    def _ctx(locale: str) -> EvalContext:
        return EvalContext(
            transcript=[{"role": "agent", "content": "Hello, how can I help?"}],
            trace_event_types=[],
            outcome="resolved",
            latency_ms=1000,
            tokens_used=100,
            turn_count=1,
            slo_seconds=300,
            tier="foundational",
            compliance_checks=[],
            ccb_pre=None,
            ccb_post=None,
            scenario_title="Test",
            persona={"venue": "pack.test.v1"},
            locale=locale,
        )

    stub = StubProvider()
    en = await p7_cx.score(_ctx("en"), stub)
    es = await p7_cx.score(_ctx("es"), stub)
    # Same run, different rubric-prompt language → the deterministic stub judge scores differently.
    assert en.score != es.score
