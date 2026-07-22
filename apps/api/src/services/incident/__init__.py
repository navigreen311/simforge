"""Incident Command — consolidated operational-health view (blueprint §H; ADR-0040)."""

from __future__ import annotations

from src.services.incident.report import incident_report

__all__ = ["incident_report"]
