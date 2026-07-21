"""Adversarial layer — automated red-team probing of agents (blueprint §L.4; ADR-0028)."""

from src.services.adversarial.probes import (
    ProbeResult,
    evaluate_probe_response,
    run_adversarial_suite,
)
from src.services.adversarial.tactics import TACTICS

__all__ = ["TACTICS", "ProbeResult", "evaluate_probe_response", "run_adversarial_suite"]
