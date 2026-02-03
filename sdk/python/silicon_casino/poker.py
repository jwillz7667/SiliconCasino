from typing import Any, Callable
from uuid import UUID

import httpx

from silicon_casino.websocket import WebSocketClient


class PokerClient:
    """Client for poker-specific operations."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        token: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        self._ws_client: WebSocketClient | None = None
        self._current_table_id: UUID | None = None

    async def __aenter__(self) -> "PokerClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self) -> None:
        """Close all connections."""
        await self._client.aclose()
        if self._ws_client:
            await self._ws_client.disconnect()

    def _headers(self) -> dict[str, str]:
        """Get headers for authenticated requests."""
        if self._token:
            return {"Authorization": f"Bearer {self._token}"}
        return {}

    async def list_tables(self) -> list[dict[str, Any]]:
        """List all active poker tables."""
        response = await self._client.get(
            "/api/poker/tables",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()["tables"]

    async def create_table(
        self,
        name: str,
        small_blind: int,
        big_blind: int,
        min_buy_in: int,
        max_buy_in: int,
        max_players: int = 6,
    ) -> dict[str, Any]:
        """Create a new poker table."""
        response = await self._client.post(
            "/api/poker/tables",
            json={
                "name": name,
                "small_blind": small_blind,
                "big_blind": big_blind,
                "min_buy_in": min_buy_in,
                "max_buy_in": max_buy_in,
                "max_players": max_players,
            },
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def get_table(self, table_id: UUID | str) -> dict[str, Any]:
        """Get detailed table state."""
        response = await self._client.get(
            f"/api/poker/tables/{table_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def join_table(
        self,
        table_id: UUID | str,
        seat_number: int,
        buy_in: int,
    ) -> dict[str, Any]:
        """Join a poker table."""
        response = await self._client.post(
            f"/api/poker/tables/{table_id}/join",
            json={"seat_number": seat_number, "buy_in": buy_in},
            headers=self._headers(),
        )
        response.raise_for_status()
        self._current_table_id = UUID(str(table_id))
        return response.json()

    async def leave_table(self, table_id: UUID | str) -> dict[str, Any]:
        """Leave a poker table."""
        response = await self._client.post(
            f"/api/poker/tables/{table_id}/leave",
            headers=self._headers(),
        )
        response.raise_for_status()
        if self._current_table_id == UUID(str(table_id)):
            self._current_table_id = None
        return response.json()

    async def action(
        self,
        table_id: UUID | str,
        action: str,
        amount: int = 0,
    ) -> dict[str, Any]:
        """Take a poker action via REST API."""
        response = await self._client.post(
            f"/api/poker/tables/{table_id}/action",
            json={"action": action, "amount": amount},
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def fold(self, table_id: UUID | str | None = None) -> dict[str, Any]:
        """Fold the current hand."""
        tid = table_id or self._current_table_id
        if not tid:
            raise ValueError("No table specified")
        return await self.action(tid, "fold")

    async def check(self, table_id: UUID | str | None = None) -> dict[str, Any]:
        """Check (if allowed)."""
        tid = table_id or self._current_table_id
        if not tid:
            raise ValueError("No table specified")
        return await self.action(tid, "check")

    async def call(self, table_id: UUID | str | None = None) -> dict[str, Any]:
        """Call the current bet."""
        tid = table_id or self._current_table_id
        if not tid:
            raise ValueError("No table specified")
        return await self.action(tid, "call")

    async def bet(self, amount: int, table_id: UUID | str | None = None) -> dict[str, Any]:
        """Make a bet."""
        tid = table_id or self._current_table_id
        if not tid:
            raise ValueError("No table specified")
        return await self.action(tid, "bet", amount)

    async def raise_to(self, amount: int, table_id: UUID | str | None = None) -> dict[str, Any]:
        """Raise to a specific amount."""
        tid = table_id or self._current_table_id
        if not tid:
            raise ValueError("No table specified")
        return await self.action(tid, "raise", amount)

    async def all_in(self, table_id: UUID | str | None = None) -> dict[str, Any]:
        """Go all-in."""
        tid = table_id or self._current_table_id
        if not tid:
            raise ValueError("No table specified")
        return await self.action(tid, "all_in")

    async def get_hand_history(
        self,
        table_id: UUID | str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get recent hand history for a table."""
        response = await self._client.get(
            f"/api/poker/tables/{table_id}/history",
            params={"limit": limit},
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()["hands"]

    async def connect_websocket(
        self,
        on_message: Callable[[dict[str, Any]], None] | None = None,
    ) -> "WebSocketClient":
        """Connect to WebSocket for real-time updates."""
        if not self._token:
            raise ValueError("Not authenticated")

        ws_base = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_base}/api/ws?token={self._token}"

        self._ws_client = WebSocketClient(ws_url, on_message)
        await self._ws_client.connect()
        return self._ws_client

    async def ws_join_table(self, table_id: UUID | str) -> None:
        """Join a table via WebSocket for real-time updates."""
        if not self._ws_client:
            raise ValueError("WebSocket not connected")
        await self._ws_client.send({
            "type": "join_table",
            "table_id": str(table_id),
        })
        self._current_table_id = UUID(str(table_id))

    async def ws_leave_table(self) -> None:
        """Leave the current table via WebSocket."""
        if not self._ws_client:
            raise ValueError("WebSocket not connected")
        await self._ws_client.send({"type": "leave_table"})
        self._current_table_id = None

    async def ws_action(self, action: str, amount: int = 0) -> None:
        """Take an action via WebSocket."""
        if not self._ws_client or not self._current_table_id:
            raise ValueError("WebSocket not connected or no table joined")
        await self._ws_client.send({
            "type": "action",
            "table_id": str(self._current_table_id),
            "action": action,
            "amount": amount,
        })

    async def ws_get_state(self) -> None:
        """Request current game state via WebSocket."""
        if not self._ws_client or not self._current_table_id:
            raise ValueError("WebSocket not connected or no table joined")
        await self._ws_client.send({
            "type": "get_state",
            "table_id": str(self._current_table_id),
        })
