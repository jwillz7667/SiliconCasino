import json
from typing import Any
from uuid import UUID

from fastapi import Query, WebSocket, WebSocketDisconnect

from backend.api.websocket.manager import manager
from backend.core.security import decode_token
from backend.game_engine.poker.betting import ActionType


class WebSocketHandler:
    """Handles WebSocket messages for the poker platform."""

    def __init__(self):
        self._table_engines: dict[UUID, Any] = {}

    def register_engine(self, table_id: UUID, engine: Any) -> None:
        """Register a poker engine for a table."""
        self._table_engines[table_id] = engine

    def unregister_engine(self, table_id: UUID) -> None:
        """Unregister a poker engine."""
        self._table_engines.pop(table_id, None)

    def get_engine(self, table_id: UUID) -> Any:
        """Get the poker engine for a table."""
        return self._table_engines.get(table_id)

    async def handle_message(
        self,
        agent_id: UUID,
        message: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Handle an incoming WebSocket message."""
        msg_type = message.get("type")

        if msg_type == "ping":
            return {"type": "pong"}

        elif msg_type == "join_table":
            table_id = message.get("table_id")
            if table_id:
                try:
                    table_uuid = UUID(table_id)
                    await manager.join_table(agent_id, table_uuid)
                    engine = self.get_engine(table_uuid)
                    if engine:
                        state = engine.get_state(for_agent=agent_id)
                        return {"type": "game_state", "data": state}
                    return {"type": "joined_table", "table_id": table_id}
                except ValueError:
                    return {"type": "error", "message": "Invalid table_id"}
            return {"type": "error", "message": "Missing table_id"}

        elif msg_type == "leave_table":
            await manager.leave_table(agent_id)
            return {"type": "left_table"}

        elif msg_type == "action":
            table_id = message.get("table_id")
            action_str = message.get("action")
            amount = message.get("amount", 0)

            if not table_id or not action_str:
                return {"type": "error", "message": "Missing table_id or action"}

            try:
                table_uuid = UUID(table_id)
                action_type = ActionType[action_str.upper()]
            except (ValueError, KeyError):
                return {"type": "error", "message": "Invalid table_id or action"}

            engine = self.get_engine(table_uuid)
            if not engine:
                return {"type": "error", "message": "Table not found"}

            try:
                engine.process_action(agent_id, action_type, amount)

                await manager.send_game_state(
                    table_uuid,
                    lambda aid: engine.get_state(for_agent=aid),
                )

                if engine.can_start_hand():
                    engine.start_hand()
                    await manager.send_game_state(
                        table_uuid,
                        lambda aid: engine.get_state(for_agent=aid),
                    )

                return None

            except ValueError as e:
                return {"type": "error", "message": str(e)}

        elif msg_type == "get_state":
            table_id = message.get("table_id")
            if table_id:
                try:
                    table_uuid = UUID(table_id)
                    engine = self.get_engine(table_uuid)
                    if engine:
                        state = engine.get_state(for_agent=agent_id)
                        return {"type": "game_state", "data": state}
                    return {"type": "error", "message": "Table not found"}
                except ValueError:
                    return {"type": "error", "message": "Invalid table_id"}
            return {"type": "error", "message": "Missing table_id"}

        return {"type": "error", "message": f"Unknown message type: {msg_type}"}


ws_handler = WebSocketHandler()


async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
) -> None:
    """WebSocket endpoint for real-time game communication."""
    try:
        payload = decode_token(token)
        agent_id = UUID(payload["sub"])
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await manager.connect(websocket, agent_id)

    try:
        await websocket.send_json({"type": "connected", "agent_id": str(agent_id)})

        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                response = await ws_handler.handle_message(agent_id, message)
                if response:
                    await websocket.send_json(response)

            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})

    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(agent_id)
