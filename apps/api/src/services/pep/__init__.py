"""Policy Enforcement Point SDK (blueprint §F.6; ADR-0024).

A PEP embeds in a Village runtime or a Forge service. It calls the PDP, caches decisions in-process
with a bounded TTL, invalidates on `simforge:revocations` events, and degrades gracefully when the
PDP is unreachable. Import `Pep` + a `DecisionSource` (HTTP to `/api/pdp/decide`, or in-process).
"""

from src.services.pep.pep import DecisionSource, Pep
from src.services.pep.sources import HttpDecisionSource, local_decision_source

__all__ = ["Pep", "DecisionSource", "HttpDecisionSource", "local_decision_source"]
