"""Forge Operation Certification — shared foundation (Batches 1 & 2).

The operation rubric (dimensions + scenario-class map + spread metric) and the 7-state operation
cert state machine. SEPARATE from the domain rubric and domain certs — this module never touches
them. Scenario running, payloads, gating, re-cert, routers, and UI are built by other streams
against this foundation.
"""

from src.services.operation.rubric import (
    DIMENSION_SCENARIO_CLASS,
    OPERATION_DIMENSIONS,
    OPERATION_RUBRIC_VERSION,
    compute_rubric_dimension_spread,
    validate_every_dimension_has_scenario_class,
)
from src.services.operation.state_machine import (
    LEGAL_TRANSITIONS,
    OPERATION_STATES,
    OperationState,
    is_assignable,
    is_recert_required,
    is_transition_legal,
)

__all__ = [
    "OPERATION_DIMENSIONS",
    "DIMENSION_SCENARIO_CLASS",
    "OPERATION_RUBRIC_VERSION",
    "compute_rubric_dimension_spread",
    "validate_every_dimension_has_scenario_class",
    "OperationState",
    "OPERATION_STATES",
    "LEGAL_TRANSITIONS",
    "is_assignable",
    "is_recert_required",
    "is_transition_legal",
]
