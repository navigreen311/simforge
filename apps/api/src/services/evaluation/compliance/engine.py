"""Compliance evaluation engine — the real P2 (§5.1, §9.1).

Evaluates the global hard-violation prohibition plus every `compliance_check` the scenario declares,
each via its rule in the catalog. Returns a structured per-rule report so the scorecard and the
Software/Village gap reports can name exactly which rule failed (not just a single bool).

P2 passes iff: no prohibition triggered AND (obligations are not being enforced OR every declared
obligation is met). Obligation enforcement is gated by `settings.compliance_enforce_obligations`
(default off) — an honest seam: obligations are always computed and reported, and become hard P2
failures once a deployment flips enforcement on for real (non-stub) agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config import settings
from src.services.evaluation.compliance.rules import (
    GLOBAL_PROHIBITION,
    PROHIBITION,
    RULES,
)
from src.services.evaluation.types import EvalContext

# status values
PASS = "pass"
FAIL = "fail"
WARN = "warn"  # obligation unmet but enforcement is off
NO_RULE = "no_rule"


@dataclass
class ComplianceResult:
    check: str
    domain: str
    kind: str
    status: str
    evidence: str

    def as_dict(self) -> dict:
        return self.__dict__


@dataclass
class ComplianceReport:
    passed: bool
    results: list[ComplianceResult] = field(default_factory=list)

    @property
    def failures(self) -> list[ComplianceResult]:
        return [r for r in self.results if r.status == FAIL]

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "results": [r.as_dict() for r in self.results],
            "failures": [r.as_dict() for r in self.failures],
        }


def evaluate_compliance(ctx: EvalContext) -> ComplianceReport:
    """Run the global prohibition + each declared check's rule → structured report + P2 verdict."""
    blob = " ".join(ctx.agent_turns).lower()
    enforce_obligations = settings.compliance_enforce_obligations
    results: list[ComplianceResult] = []
    passed = True

    # 1) Global hard-violation backstop (always a prohibition).
    ok, evidence = GLOBAL_PROHIBITION.evaluate(blob)
    results.append(
        ComplianceResult(
            GLOBAL_PROHIBITION.check,
            GLOBAL_PROHIBITION.domain,
            PROHIBITION,
            PASS if ok else FAIL,
            evidence,
        )
    )
    if not ok:
        passed = False

    # 2) Each declared compliance check.
    for check in ctx.compliance_checks:
        rule = RULES.get(check)
        if rule is None:
            # Unknown check — surfaced honestly (not silently passed), but doesn't fail P2.
            results.append(
                ComplianceResult(
                    check, "unknown", NO_RULE, NO_RULE, "no rule catalogued for this check"
                )
            )
            continue
        ok, evidence = rule.evaluate(blob)
        if rule.kind == PROHIBITION:
            status = PASS if ok else FAIL
            if not ok:
                passed = False
        else:  # OBLIGATION
            if ok:
                status = PASS
            elif enforce_obligations:
                status = FAIL
                passed = False
            else:
                status = WARN
        results.append(ComplianceResult(check, rule.domain, rule.kind, status, evidence))

    return ComplianceReport(passed=passed, results=results)
