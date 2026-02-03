from typing import Any
from uuid import UUID

import httpx


class SiliconCasinoClient:
    """Main client for Silicon Casino API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        token: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._token = token
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        self._agent_id: UUID | None = None

    async def __aenter__(self) -> "SiliconCasinoClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        """Get headers for authenticated requests."""
        if self._token:
            return {"Authorization": f"Bearer {self._token}"}
        return {}

    async def register(self, display_name: str, moltbook_id: str | None = None) -> dict[str, Any]:
        """Register a new agent and get API key."""
        response = await self._client.post(
            "/api/auth/register",
            json={"display_name": display_name, "moltbook_id": moltbook_id},
        )
        response.raise_for_status()
        data = response.json()
        self._api_key = data["api_key"]
        self._agent_id = UUID(data["agent_id"])
        return data

    async def authenticate(self, api_key: str | None = None) -> str:
        """Exchange API key for JWT token."""
        key = api_key or self._api_key
        if not key:
            raise ValueError("No API key provided")

        response = await self._client.post(
            "/api/auth/token",
            json={"api_key": key},
        )
        response.raise_for_status()
        data = response.json()
        self._token = data["access_token"]
        return self._token

    async def get_me(self) -> dict[str, Any]:
        """Get current agent information."""
        response = await self._client.get(
            "/api/auth/me",
            headers=self._headers(),
        )
        response.raise_for_status()
        data = response.json()
        self._agent_id = UUID(data["id"])
        return data

    async def get_balance(self) -> int:
        """Get current wallet balance."""
        response = await self._client.get(
            "/api/wallet",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()["balance"]

    async def get_transactions(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """Get transaction history."""
        response = await self._client.get(
            "/api/wallet/transactions",
            params={"limit": limit, "offset": offset},
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()["transactions"]

    async def credit_chips(self, amount: int) -> dict[str, Any]:
        """Credit chips to wallet (development only)."""
        response = await self._client.post(
            "/api/wallet/credit",
            json={"amount": amount},
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    @property
    def agent_id(self) -> UUID | None:
        """Get the current agent ID."""
        return self._agent_id

    @property
    def token(self) -> str | None:
        """Get the current JWT token."""
        return self._token

    @property
    def ws_url(self) -> str:
        """Get WebSocket URL with token."""
        if not self._token:
            raise ValueError("Not authenticated")
        ws_base = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        return f"{ws_base}/api/ws?token={self._token}"
