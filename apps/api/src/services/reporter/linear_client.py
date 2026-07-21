"""Linear client for gap-ticket routing (blueprint §C.11; ADR-0029).

Dev is a no-op (empty `LINEAR_API_KEY` → return an empty ticket, nothing posted). With a key + team
id, it creates a real Linear issue via the GraphQL API. **Best-effort**: a Linear outage or error is
logged and returns an empty ticket — it never blocks gap emission. An injectable httpx transport
makes the real path hermetically testable.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from src.config import settings
from src.telemetry.logging import get_logger

log = get_logger("linear_client")

_ISSUE_CREATE = """
mutation IssueCreate($input: IssueCreateInput!) {
  issueCreate(input: $input) { success issue { id identifier url } }
}
"""


@dataclass
class LinearTicket:
    linear_id: str | None
    linear_url: str | None


class LinearClient:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.api_key = getattr(settings, "linear_api_key", "") or ""
        self.team_id = getattr(settings, "linear_team_id", "") or ""
        self.api_url = getattr(settings, "linear_api_url", "https://api.linear.app/graphql")
        self._transport = transport

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.team_id)

    async def create_ticket(
        self, project: str, title: str, description: str, metadata: dict
    ) -> LinearTicket:
        if not self.enabled:
            log.info("linear_skip", project=project, title=title[:60])
            return LinearTicket(linear_id=None, linear_url=None)

        body = description
        if metadata:
            body += "\n\n---\n" + "\n".join(f"- **{k}:** {v}" for k, v in metadata.items())
        variables = {
            "input": {"teamId": self.team_id, "title": f"[{project}] {title}", "description": body}
        }
        try:
            async with httpx.AsyncClient(timeout=10.0, transport=self._transport) as c:
                resp = await c.post(
                    self.api_url,
                    json={"query": _ISSUE_CREATE, "variables": variables},
                    headers={"Authorization": self.api_key, "Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:  # best-effort — never break gap emission
            log.warning("linear_post_failed", error=type(exc).__name__, title=title[:60])
            return LinearTicket(linear_id=None, linear_url=None)

        payload = (data.get("data") or {}).get("issueCreate") or {}
        if not payload.get("success"):
            log.warning("linear_create_unsuccessful", errors=str(data.get("errors"))[:200])
            return LinearTicket(linear_id=None, linear_url=None)
        issue = payload.get("issue") or {}
        return LinearTicket(linear_id=issue.get("id"), linear_url=issue.get("url"))
