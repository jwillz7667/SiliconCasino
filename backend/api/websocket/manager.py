import asyncio
import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from fastapi import WebSocket


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""

    websocket: WebSocket
    agent_id: UUID
    table_id: UUID | None = None


class ConnectionManager:
    """Manages WebSocket connections for the poker platform."""

    def __init__(self):
        self._connections: dict[UUID, ConnectionInfo] = {}
        self._table_connections: dict[UUID, set[UUID]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, agent_id: UUID) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections[agent_id] = ConnectionInfo(
                websocket=websocket,
                agent_id=agent_id,
            )

    async def disconnect(self, agent_id: UUID) -> None:
        """Handle disconnection."""
        async with self._lock:
            conn = self._connections.pop(agent_id, None)
            if conn and conn.table_id:
                table_conns = self._table_connections.get(conn.table_id)
                if table_conns:
                    table_conns.discard(agent_id)

    async def join_table(self, agent_id: UUID, table_id: UUID) -> None:
        """Associate a connection with a table."""
        async with self._lock:
            conn = self._connections.get(agent_id)
            if conn:
                if conn.table_id:
                    old_conns = self._table_connections.get(conn.table_id)
                    if old_conns:
                        old_conns.discard(agent_id)

                conn.table_id = table_id
                if table_id not in self._table_connections:
                    self._table_connections[table_id] = set()
                self._table_connections[table_id].add(agent_id)

    async def leave_table(self, agent_id: UUID) -> None:
        """Remove a connection from its table."""
        async with self._lock:
            conn = self._connections.get(agent_id)
            if conn and conn.table_id:
                table_conns = self._table_connections.get(conn.table_id)
                if table_conns:
                    table_conns.discard(agent_id)
                conn.table_id = None

    async def send_personal(self, agent_id: UUID, message: dict[str, Any]) -> bool:
        """Send a message to a specific agent."""
        conn = self._connections.get(agent_id)
        if conn:
            try:
                await conn.websocket.send_json(message)
                return True
            except Exception:
                await self.disconnect(agent_id)
        return False

    async def broadcast_to_table(
        self,
        table_id: UUID,
        message: dict[str, Any],
        exclude: UUID | None = None,
    ) -> int:
        """Broadcast a message to all agents at a table."""
        agent_ids = self._table_connections.get(table_id, set()).copy()
        if exclude:
            agent_ids.discard(exclude)

        sent_count = 0
        for agent_id in agent_ids:
            if await self.send_personal(agent_id, message):
                sent_count += 1

        return sent_count

    async def send_game_state(
        self,
        table_id: UUID,
        get_state_func,
    ) -> None:
        """Send personalized game state to each player at a table."""
        agent_ids = self._table_connections.get(table_id, set()).copy()

        for agent_id in agent_ids:
            state = get_state_func(agent_id)
            message = {
                "type": "game_state",
                "data": state,
            }
            await self.send_personal(agent_id, message)

    def get_table_agent_ids(self, table_id: UUID) -> set[UUID]:
        """Get all agent IDs connected to a table."""
        return self._table_connections.get(table_id, set()).copy()

    def is_connected(self, agent_id: UUID) -> bool:
        """Check if an agent is connected."""
        return agent_id in self._connections

    def get_connection_count(self) -> int:
        """Get total number of connections."""
        return len(self._connections)


manager = ConnectionManager()
