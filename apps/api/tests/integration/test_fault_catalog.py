"""Fault catalog — deterministic plain-language gap descriptions (Gaps plain-language PR)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.gap import SoftwareGap
from src.services.reporter.fault_catalog import (
    FAULT_CATALOG,
    describe_gap,
    extract_fault_code,
)
from src.utils.time import utcnow

# The exact (forge, module, machine-summary) shapes present in the seed data.
SEED = [
    (
        "vaf",
        "doc_vault",
        "vaf.doc_vault returned a 'forged_signature' fault during the run",
        "forged_signature",
    ),
    (
        "voiceforge",
        "call_center",
        "voiceforge.call_center returned a 'dropped_call' fault during the run",
        "dropped_call",
    ),
    (
        "cre-forge",
        "deals",
        "cre-forge.deals returned a 'title_defect' fault during the run",
        "title_defect",
    ),
    (
        "medlink-pro",
        "scheduler",
        "medlink-pro.scheduler returned a 'shift_double_booked' fault during the run",
        "shift_double_booked",
    ),
    (
        "medlink-pro",
        "compliance",
        "medlink-pro.compliance returned a 'credential_expired_unflagged' fault during the run",
        "credential_expired_unflagged",
    ),
    (
        "capitalforge",
        "emd",
        "capitalforge.emd returned a 'fraud_flag' fault during the run",
        "fraud_flag",
    ),
    (
        "funnelforge",
        "sequences",
        "funnelforge.sequences returned a 'sequence_misfire' fault during the run",
        "sequence_misfire",
    ),
    (
        "cre-forge",
        "deals",
        "cre-forge.deals degrades under crisis load",
        "degrades_under_crisis_load",
    ),
    (
        "voiceforge",
        "call_center",
        "voiceforge.call_center did not complete within SLO",
        "slo_exceeded",
    ),
]


@pytest.mark.parametrize("forge,module,summary,code", SEED)
def test_every_seed_code_has_a_catalog_entry(forge, module, summary, code) -> None:  # noqa: ANN001
    assert extract_fault_code(summary) == code
    assert code in FAULT_CATALOG, f"seed fault_code {code} missing from catalog"
    d = describe_gap(forge, module, summary)
    assert d["code"] == code
    for field in ("what", "why", "action"):
        assert d[field] and len(d[field]) > 10  # never blank
    # No jargon / no fault-code names / no "during the run" in the plain 'what'.
    assert "during the run" not in d["what"]
    assert code not in d["what"]


def test_unknown_fault_falls_back_readably() -> None:
    d = describe_gap(
        "newforge", "widgets", "newforge.widgets returned a 'gizmo_overheat' fault during the run"
    )
    assert d["code"] == "gizmo_overheat"
    assert "gizmo overheat" in d["what"].lower()  # humanized, de-underscored
    assert d["why"] and d["action"]  # never blank
    assert "catalog" in d["action"].lower()


def test_unparseable_summary_still_produces_text() -> None:
    d = describe_gap("x", "y", "x.y something entirely unexpected happened")
    assert d["code"] is None
    assert d["what"].startswith("Something entirely unexpected")  # prefix stripped, capitalized
    assert d["why"] and d["action"]


async def test_api_serves_plain_and_technical(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    now = utcnow()
    db_session.add(
        SoftwareGap(
            ticketId="SF-GAP-9001",
            runId="run-x",
            forge="medlink-pro",
            module="compliance",
            severity="P1",
            summary=(
                "medlink-pro.compliance returned a 'credential_expired_unflagged' fault "
                "during the run"
            ),
            detail="d",
            status="open",
            firstSeenRunId="run-x",
            lastSeenRunId="run-x",
            occurrenceCount=1,
            createdAt=now,
            updatedAt=now,
        )
    )
    await db_session.commit()

    body = (await client.get("/api/gaps/software")).json()
    gap = next(g for g in body["items"] if g["ticketId"] == "SF-GAP-9001")

    # Raw string preserved (both the legacy field and the explicit one).
    assert "credential_expired_unflagged" in gap["summary"]
    assert gap["summary_technical"] == gap["summary"]
    # Plain-language object present and human.
    assert gap["summary_plain"]["code"] == "credential_expired_unflagged"
    assert "license or certification expired" in gap["summary_plain"]["what"]
    assert "HCQC" in gap["summary_plain"]["why"]
    assert gap["summary_plain"]["action"]
