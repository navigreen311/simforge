"""Golden Benchmark suite (blueprint §L.4 v1.2 deferral; ADR-0033)."""

from __future__ import annotations

from src.services.golden.suite import (
    DEFAULT_BASELINE_PATH,
    compute_golden,
    load_baseline,
    run_golden_suite,
)

__all__ = [
    "DEFAULT_BASELINE_PATH",
    "compute_golden",
    "load_baseline",
    "run_golden_suite",
]
