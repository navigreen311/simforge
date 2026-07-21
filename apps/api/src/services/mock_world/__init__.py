"""Mock world — personas + Forge stubs the agent interacts with (blueprint §C.2).

v1: an in-process deterministic persona responder + a recorded (no-op) Forge action log.
HTTP Forge sandbox stubs land with the Forge adapters in a later phase.
"""

from src.services.mock_world.world import MockWorld

__all__ = ["MockWorld"]
