"""Multi-agent handoff integrity (v1.1).

Department work crosses agents: outreach hands a lead to underwriting, underwriting hands a decision
to servicing. A handoff has integrity when nothing the receiver needs is dropped, the chain doesn't
skip a link, and consent travels with the work. This evaluates an ordered chain of handoff steps and
reports exactly where integrity breaks — deterministic, so it can gate a department-level cert.

Each step: {from, to, provides: [field], required: [field], consent: bool}. A step is complete when
every `required` field is in `provides`; the chain is continuous when each step's `to` is the next
step's `from`; consent must be carried on every step that moves work.
"""

from __future__ import annotations


def evaluate(chain: list[dict]) -> dict:
    findings: list[dict] = []

    for i, step in enumerate(chain):
        frm = str(step.get("from", ""))
        to = str(step.get("to", ""))
        provides = {str(f) for f in step.get("provides", [])}
        required = [str(f) for f in step.get("required", [])]
        consent = bool(step.get("consent", False))

        missing = [f for f in required if f not in provides]
        if missing:
            findings.append(
                {
                    "step": i,
                    "from": frm,
                    "to": to,
                    "kind": "incomplete_handoff",
                    "detail": f"{to} requires {missing} but {frm} did not provide it.",
                }
            )
        if not consent:
            findings.append(
                {
                    "step": i,
                    "from": frm,
                    "to": to,
                    "kind": "missing_consent",
                    "detail": f"Consent did not travel with the handoff from {frm} to {to}.",
                }
            )
        # Continuity: this step's receiver must be the next step's sender.
        if i + 1 < len(chain):
            next_from = str(chain[i + 1].get("from", ""))
            if to != next_from:
                findings.append(
                    {
                        "step": i,
                        "from": frm,
                        "to": to,
                        "kind": "broken_continuity",
                        "detail": (
                            f"Chain breaks: step {i} hands to {to}, "
                            f"but step {i + 1} starts from {next_from}."
                        ),
                    }
                )

    steps = len(chain)
    return {
        "steps": steps,
        "findings": findings,
        "passed": len(findings) == 0,
        "integrity_score": round((steps - len({f["step"] for f in findings})) / steps, 3)
        if steps
        else 1.0,
        "summary": {
            "incomplete": sum(1 for f in findings if f["kind"] == "incomplete_handoff"),
            "missing_consent": sum(1 for f in findings if f["kind"] == "missing_consent"),
            "broken_continuity": sum(1 for f in findings if f["kind"] == "broken_continuity"),
        },
    }
