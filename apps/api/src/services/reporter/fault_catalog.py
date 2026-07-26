"""Fault catalog — deterministic plain-language descriptions of Forge faults.

A governance/certification console must describe defects the *same way every time*: no LLM, no
variance, auditable. This module maps a Forge fault to a three-part operator-readable description
(what broke / why it matters / what to do), derived at response time from the (forge, module,
fault_code). Nothing is persisted — the text is a pure function of the catalog.

The fault_code is extracted from the reporter's machine summary (see `software_gap.py`), which has
three shapes:
  - ``{forge}.{module} returned a '{code}' fault during the run``  → code
  - ``{forge}.{module} degrades under crisis load``               → ``degrades_under_crisis_load``
  - ``{forge}.{module} did not complete within SLO``              → ``slo_exceeded``
"""

from __future__ import annotations

import re

# Keyed by fault_code. Every code present in the seed data has an entry (proven by the distinct-set
# query in the PR). A (forge, module) override could be layered on top later; today codes are
# globally meaningful, so a code key is sufficient and unambiguous.
FAULT_CATALOG: dict[str, dict[str, str]] = {
    "forged_signature": {
        "what": "A document came through with a signature that failed verification — it may have "
        "been altered or faked.",
        "why": "If a forged document is accepted, a deal or record could be built on a fraudulent "
        "basis. This is a trust-and-safety failure, not a cosmetic one.",
        "action": "The Document Vault should have rejected this. Confirm the verification step is "
        "actually blocking, not just warning.",
    },
    "credential_expired_unflagged": {
        "what": "A clinician's license or certification expired and the system did not flag it.",
        "why": "An expired-credential clinician being marked available for a shift is a licensure "
        "and liability exposure — exactly the kind of miss a Nevada HCQC audit looks for.",
        "action": "Compliance should hard-block expired credentials from the available pool. "
        "Verify the expiry check runs before dispatch, not after.",
    },
    "shift_double_booked": {
        "what": "The scheduler assigned the same clinician to two overlapping shifts.",
        "why": "A double-booked clinician means one facility gets no coverage — a direct service "
        "failure and a reputational hit.",
        "action": "The scheduler needs an overlap guard that rejects the second assignment. Check "
        "whether the conflict check is missing or just not enforced.",
    },
    "title_defect": {
        "what": "A property title problem surfaced on a deal — a lien, ownership gap, or "
        "encumbrance.",
        "why": "A title defect caught late can kill a deal at closing or expose the assignment to "
        "a claim. Catching it early is the whole value of the walkthrough.",
        "action": "Confirm the deal pipeline surfaces title issues before an assignment is "
        "written, not days before closing.",
    },
    "dropped_call": {
        "what": "An outbound voice call was cut off mid-conversation.",
        "why": "A dropped call to a facility or clinician can mean a missed placement or a "
        "frustrated contact. Under load it compounds.",
        "action": "Check the call-center voice path for connection stability, especially under "
        "concurrent call volume.",
    },
    "fraud_flag": {
        "what": "An earnest-money / funding transaction tripped a fraud signal.",
        "why": "A fraud flag on capital movement has to be resolved before funds release — a false "
        "positive stalls a deal, a true positive stops a loss.",
        "action": "Confirm flagged transactions halt and route for review rather than proceeding "
        "automatically.",
    },
    "sequence_misfire": {
        "what": "A marketing follow-up sequence fired the wrong step or skipped one.",
        "why": "A lead getting the wrong message (or none) is a lost conversion and can read as "
        "unprofessional.",
        "action": "Check the sequence step logic for ordering and skip conditions.",
    },
    "degrades_under_crisis_load": {
        "what": "This module still works, but slows down or gets less reliable when the scenario "
        "puts it under heavy simultaneous load.",
        "why": "Crisis load is exactly when the system matters most — an audit, a mass-callout, a "
        "closing crunch. Degrading then is a real-world failure even if nothing 'errors'.",
        "action": "This is a performance/resilience issue, not a correctness bug. Profile the "
        "module under concurrency and find the bottleneck.",
    },
    "slo_exceeded": {
        "what": "The task did not finish within its expected time budget.",
        "why": "A step that runs long ties up a placement, a call, or a closing — the operator is "
        "left waiting and downstream work stalls.",
        "action": "Investigate the module's latency and timeout handling; find what is running "
        "long under this scenario.",
    },
}


def extract_fault_code(summary: str) -> str | None:
    """Recover the fault_code from a reporter machine summary (see module docstring for shapes)."""
    m = re.search(r"returned a '([^']+)' fault", summary)
    if m:
        return m.group(1)
    if "degrades under crisis load" in summary:
        return "degrades_under_crisis_load"
    if "did not complete within SLO" in summary:
        return "slo_exceeded"
    return None


def _humanize(module: str, code: str | None, summary: str) -> str:
    """Readable rephrase for an uncatalogued fault — strip module prefix, de-underscore the code."""
    if code:
        return f"A '{code.replace('_', ' ')}' issue was surfaced in {module}."
    # No code recoverable: strip a leading "forge.module " prefix from the raw summary.
    cleaned = re.sub(r"^[a-z0-9_-]+\.[a-z0-9_-]+\s+", "", summary).strip()
    return cleaned[0].upper() + cleaned[1:] if cleaned else "An unclassified fault was surfaced."


def describe_gap(forge: str, module: str, summary: str) -> dict[str, str | None]:
    """Plain-language {code, what, why, action} for a gap. Never returns empty fields."""
    code = extract_fault_code(summary)
    entry = FAULT_CATALOG.get(code or "")
    if entry is not None:
        return {"code": code, **entry}
    # Graceful, readable fallback — never blank.
    return {
        "code": code,
        "what": _humanize(module, code, summary),
        "why": "Surfaced by a scenario run. Impact not yet catalogued.",
        "action": "Add this fault to the fault catalog so it gets a proper description.",
    }
