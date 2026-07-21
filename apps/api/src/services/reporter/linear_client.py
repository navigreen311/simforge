"""Linear client for gap-ticket routing (blueprint §C.11).

Dev is a no-op (empty LINEAR_API_KEY → don't post, just return None). The real client
(httpx to the Linear GraphQL API) drops in behind `create_ticket` in staging/prod.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config import settings
from src.telemetry.logging import get_logger

log = get_logger("linear_client")


@dataclass
class LinearTicket:
    linear_id: str | None
    linear_url: str | None


class LinearClient:
    def __init__(self) -> None:
        self.api_key = getattr(settings, "linear_api_key", "") or ""

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def create_ticket(
        self, project: str, title: str, description: str, metadata: dict
    ) -> LinearTicket:
        if not self.enabled:
            log.info("linear_skip", project=project, title=title[:60])
            return LinearTicket(linear_id=None, linear_url=None)
        # WEEK 9: POST to Linear GraphQL; return created issue id + url.
        raise NotImplementedError("Live Linear posting not enabled in this environment")
