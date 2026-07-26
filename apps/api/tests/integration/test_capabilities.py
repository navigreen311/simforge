"""Capability catalog — friendly labels for Forge-capability ids (readiness-matrix PR)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.services.capabilities import describe_capability

# The 10 distinct capability columns present in the seed data + the label each should get.
SEED = [
    ("cre-forge.call_center.outbound_seller_outreach", "cre-forge", "Outbound Seller Outreach"),
    ("capitalforge.emd.release", "capitalforge", "Earnest Money Release"),
    ("funnelforge.sequences.trigger", "funnelforge", "Marketing Sequence Trigger"),
    ("vaf.doc_vault.retrieve", "vaf", "Document Retrieval"),
    ("voiceforge.call_center.inbound", "voiceforge", "Inbound Call Handling"),
    ("voiceforge.call_center.outbound", "voiceforge", "Outbound Calling"),
    ("capitalforge.demo.pdp_fresh_cap_001", "capitalforge", "Demo capability (seed data)"),
    ("capitalforge.demo.pdp_pep_28459c1d", "capitalforge", "Demo capability (seed data)"),
    ("capitalforge.demo.pdp_pep_loop", "capitalforge", "Demo capability (seed data)"),
    ("capitalforge.demo.train_1784667286", "capitalforge", "Demo capability (seed data)"),
]


@pytest.mark.parametrize("cap_id,forge,label", SEED)
def test_seed_capabilities_have_readable_labels(cap_id, forge, label) -> None:  # noqa: ANN001
    d = describe_capability(cap_id)
    assert d["forge"] == forge
    assert d["label"] == label
    assert d["label"] != cap_id  # never the bare machine id
    assert "cap_id" in d and d["cap_id"] == cap_id  # raw id preserved for engineers


def test_unknown_capability_is_humanized_not_raw() -> None:
    d = describe_capability("someforge.widgets.frobnicate_the_thing")
    assert d["forge"] == "someforge"
    assert d["label"] == "Frobnicate The Thing"
    assert "." not in d["label"]


async def test_capabilities_endpoint(client: AsyncClient) -> None:
    body = (await client.get("/api/capabilities/")).json()
    caps = body["capabilities"]
    # Known catalog entries are always present.
    assert caps["capitalforge.emd.release"]["label"] == "Earnest Money Release"
    assert caps["vaf.doc_vault.retrieve"]["forge"] == "vaf"
