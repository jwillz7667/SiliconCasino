"""
Moltbook identity verification service.

Integrates with Moltbook API to verify agent identities
and sync reputation/karma data.
"""

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class MoltbookAgent:
    """Moltbook agent identity data."""

    id: str
    name: str
    description: str | None
    karma: int
    is_claimed: bool
    owner_handle: str | None
    follower_count: int
    post_count: int

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "MoltbookAgent":
        """Create from Moltbook API response."""
        owner = data.get("owner", {})
        stats = data.get("stats", {})

        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            karma=data.get("karma", 0),
            is_claimed=data.get("is_claimed", False),
            owner_handle=owner.get("xHandle") if owner else None,
            follower_count=stats.get("subscriptions", 0),
            post_count=stats.get("posts", 0),
        )


class MoltbookService:
    """Service for interacting with Moltbook API."""

    BASE_URL = "https://www.moltbook.com/api/v1"

    def __init__(self, timeout: float = 10.0):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=timeout,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def verify_agent(self, api_key: str) -> MoltbookAgent | None:
        """
        Verify an agent's identity using their Moltbook API key.

        Returns MoltbookAgent if valid, None if invalid.
        """
        try:
            response = await self._client.get(
                "/agents/me",
                headers={"Authorization": f"Bearer {api_key}"},
            )

            if response.status_code != 200:
                return None

            data = response.json()
            if not data.get("success"):
                return None

            return MoltbookAgent.from_api_response(data["agent"])

        except Exception:
            return None

    async def get_agent_by_name(self, name: str) -> MoltbookAgent | None:
        """
        Look up an agent by their Moltbook username.
        """
        try:
            response = await self._client.get(f"/agents/{name}")

            if response.status_code != 200:
                return None

            data = response.json()
            if not data.get("success"):
                return None

            return MoltbookAgent.from_api_response(data["agent"])

        except Exception:
            return None

    async def get_karma(self, api_key: str) -> int:
        """Get current karma for an agent."""
        agent = await self.verify_agent(api_key)
        return agent.karma if agent else 0


# Global instance
moltbook_service = MoltbookService()
