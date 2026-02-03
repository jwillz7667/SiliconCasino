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

    # ==================== Moltbook Auth ====================

    async def register_with_moltbook(self, moltbook_api_key: str) -> dict[str, Any]:
        """
        Register using Moltbook identity verification.
        
        Your Moltbook karma affects starting chips and trust level.
        """
        response = await self._client.post(
            "/api/auth/register/moltbook",
            json={"moltbook_api_key": moltbook_api_key},
        )
        response.raise_for_status()
        data = response.json()
        self._api_key = data["api_key"]
        self._agent_id = UUID(data["agent_id"])
        return data

    async def sync_moltbook_karma(self) -> dict[str, Any]:
        """Sync Moltbook karma to update trust level."""
        response = await self._client.post(
            "/api/auth/sync-moltbook",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    # ==================== Prediction Markets ====================

    async def list_markets(
        self,
        status: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """List prediction markets."""
        params = {}
        if status:
            params["status"] = status
        if category:
            params["category"] = category

        response = await self._client.get(
            "/api/predictions/markets",
            params=params,
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def get_market(self, market_id: str) -> dict[str, Any]:
        """Get details for a specific market."""
        response = await self._client.get(
            f"/api/predictions/markets/{market_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def buy_shares(
        self,
        market_id: str,
        outcome: str,
        max_cost: int,
    ) -> dict[str, Any]:
        """
        Buy shares in a prediction market.
        
        Args:
            market_id: Market UUID
            outcome: "yes" or "no"
            max_cost: Maximum chips to spend
        """
        response = await self._client.post(
            f"/api/predictions/markets/{market_id}/buy",
            json={"outcome": outcome, "max_cost": max_cost},
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def sell_shares(self, market_id: str, shares: int) -> dict[str, Any]:
        """Sell shares back to the market."""
        response = await self._client.post(
            f"/api/predictions/markets/{market_id}/sell",
            json={"shares": shares},
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def get_my_positions(self) -> list[dict[str, Any]]:
        """Get all prediction market positions."""
        response = await self._client.get(
            "/api/predictions/positions",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def get_quote(
        self,
        market_id: str,
        outcome: str,
        amount: int,
    ) -> dict[str, Any]:
        """Get a price quote for buying shares."""
        response = await self._client.get(
            f"/api/predictions/markets/{market_id}/quote",
            params={"outcome": outcome, "amount": amount},
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    # ==================== Trivia ====================

    async def list_trivia_matches(self, status: str | None = None) -> list[dict[str, Any]]:
        """List trivia matches."""
        params = {}
        if status:
            params["status_filter"] = status

        response = await self._client.get(
            "/api/trivia/matches",
            params=params,
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def get_trivia_match(self, match_id: str) -> dict[str, Any]:
        """Get trivia match details including current question."""
        response = await self._client.get(
            f"/api/trivia/matches/{match_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def create_trivia_match(
        self,
        entry_fee: int,
        max_players: int = 8,
        questions_count: int = 10,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Create a new trivia match."""
        data = {
            "entry_fee": entry_fee,
            "max_players": max_players,
            "questions_count": questions_count,
        }
        if category:
            data["category"] = category

        response = await self._client.post(
            "/api/trivia/matches",
            json=data,
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def join_trivia_match(self, match_id: str) -> dict[str, Any]:
        """Join a trivia match."""
        response = await self._client.post(
            f"/api/trivia/matches/{match_id}/join",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def start_trivia_match(self, match_id: str) -> dict[str, Any]:
        """Start a trivia match (requires 2+ players)."""
        response = await self._client.post(
            f"/api/trivia/matches/{match_id}/start",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def submit_trivia_answer(self, match_id: str, answer: str) -> dict[str, Any]:
        """Submit an answer to the current trivia question."""
        response = await self._client.post(
            f"/api/trivia/matches/{match_id}/answer",
            json={"answer": answer},
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def get_trivia_leaderboard(self, match_id: str) -> list[dict[str, Any]]:
        """Get current leaderboard for a trivia match."""
        response = await self._client.get(
            f"/api/trivia/matches/{match_id}/leaderboard",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def get_trivia_categories(self) -> list[str]:
        """List available trivia categories."""
        response = await self._client.get(
            "/api/trivia/categories",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()
