"""Emergency safe-mode (blueprint §F, runbook R-004).

v1 is an in-process flag (per-worker) — activating it halts new cert issuance and new runs.
v1.1 persists it + broadcasts via Redis so all processes honor it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SafeMode:
    active: bool = False
    reason: str | None = None
    activated_by: str | None = None
    _domains: set[str] = field(default_factory=set)

    def activate(self, actor: str, reason: str, domains: list[str] | None = None) -> None:
        self.active = True
        self.activated_by = actor
        self.reason = reason
        self._domains = set(domains or [])

    def deactivate(self) -> None:
        self.active = False
        self.reason = None
        self.activated_by = None
        self._domains = set()

    def status(self) -> dict:
        return {
            "active": self.active,
            "reason": self.reason,
            "activated_by": self.activated_by,
            "domains": sorted(self._domains),
        }


# Process-wide singleton.
safe_mode = SafeMode()
