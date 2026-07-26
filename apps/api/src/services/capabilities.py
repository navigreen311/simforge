"""Capability catalog — deterministic friendly labels for Forge-capability ids.

The Readiness Matrix (and any other consumer) shows columns like
``cre-forge.call_center.outbound_seller_outreach``. This maps a capability id to an
operator-readable label + one-line description, derived purely from the id — no LLM, no storage.

A capability id is ``{forge}.{module}.{action}`` (occasionally deeper, e.g. ``…demo.pdp_pep_loop``).
Unknown ids fall back readably: ``*.demo.*`` ids are seed/test placeholders; everything else is
title-cased from its trailing segments so a column is never a bare machine string.
"""

from __future__ import annotations

# Keyed by full capability id. Covers every capability currently referenced by the seed certs
# (proven by the distinct-set query in the PR). label = the human name; description = plain gloss.
CAPABILITY_CATALOG: dict[str, dict[str, str]] = {
    "cre-forge.call_center.outbound_seller_outreach": {
        "label": "Outbound Seller Outreach",
        "description": "calling property owners",
    },
    "capitalforge.emd.release": {
        "label": "Earnest Money Release",
        "description": "moving deposit funds",
    },
    "funnelforge.sequences.trigger": {
        "label": "Marketing Sequence Trigger",
        "description": "firing follow-ups",
    },
    "vaf.doc_vault.retrieve": {
        "label": "Document Retrieval",
        "description": "pulling records from the Vault",
    },
    "voiceforge.call_center.inbound": {
        "label": "Inbound Call Handling",
        "description": "answering incoming calls",
    },
    "voiceforge.call_center.outbound": {
        "label": "Outbound Calling",
        "description": "placing outbound calls",
    },
}


def _titleize(segment: str) -> str:
    return " ".join(w.capitalize() for w in segment.replace("_", " ").split())


def describe_capability(cap_id: str) -> dict[str, str]:
    """Friendly {cap_id, forge, label, description} for a capability id. Never the bare id."""
    forge = cap_id.split(".", 1)[0] if "." in cap_id else cap_id
    entry = CAPABILITY_CATALOG.get(cap_id)
    if entry is not None:
        return {"cap_id": cap_id, "forge": forge, **entry}

    parts = cap_id.split(".")
    if "demo" in parts:
        return {
            "cap_id": cap_id,
            "forge": forge,
            "label": "Demo capability (seed data)",
            "description": "placeholder capability from seed/test runs",
        }

    # Humanize the trailing 1–2 segments (drop the forge prefix).
    tail = parts[1:] if len(parts) > 1 else parts
    label = _titleize(tail[-1]) if tail else _titleize(cap_id)
    return {"cap_id": cap_id, "forge": forge, "label": label, "description": ""}
