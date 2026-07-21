"""Forge integrations (blueprint Part E). v1 ships the first real adapter: CapitalForge
(Mock Bank), in-process + deterministic. Other Forges resolve to a NullForgeAdapter until wired."""

from src.services.forges.base import Fault, FaultType, ForgeAdapter, SandboxTenant
from src.services.forges.registry import get_forge_adapter

__all__ = ["ForgeAdapter", "SandboxTenant", "Fault", "FaultType", "get_forge_adapter"]
