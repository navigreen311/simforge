"""Run orchestration — creates a Run, executes the scenario, persists results."""

from src.services.runner.execute import RunnerError, run_scenario

__all__ = ["run_scenario", "RunnerError"]
