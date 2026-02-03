"""
Spectator API routes.

Provides endpoints for humans to watch agent poker games.
"""

from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.services.spectator import SPECTATOR_DELAY_SECONDS, spectator_manager

router = APIRouter()


class TableViewerInfo(BaseModel):
    """Information about a table for spectators."""

    table_id: UUID
    spectator_count: int
    delay_seconds: int = SPECTATOR_DELAY_SECONDS


class SpectatorStatsResponse(BaseModel):
    """Statistics about spectator activity."""

    total_spectators: int
    tables_being_watched: int
    delay_seconds: int = SPECTATOR_DELAY_SECONDS


@router.get("/stats", response_model=SpectatorStatsResponse)
async def get_spectator_stats() -> SpectatorStatsResponse:
    """Get overall spectator statistics."""
    total = sum(
        spectator_manager.get_spectator_count(table_id)
        for table_id in spectator_manager._spectators.keys()
    )

    return SpectatorStatsResponse(
        total_spectators=total,
        tables_being_watched=len(spectator_manager._spectators),
    )


@router.get("/table/{table_id}", response_model=TableViewerInfo)
async def get_table_viewer_info(table_id: UUID) -> TableViewerInfo:
    """Get spectator info for a specific table."""
    return TableViewerInfo(
        table_id=table_id,
        spectator_count=spectator_manager.get_spectator_count(table_id),
    )


@router.websocket("/ws/{table_id}")
async def spectator_websocket(
    websocket: WebSocket,
    table_id: UUID,
) -> None:
    """
    WebSocket endpoint for spectating a poker table.

    Events are delayed by 30 seconds to prevent information leakage.
    Spectators see:
    - Player actions (fold, call, raise)
    - Community cards
    - Pot size
    - Hand results and showdowns

    Spectators do NOT see:
    - Hole cards (until showdown)
    - Private game state
    """
    await spectator_manager.connect(websocket, table_id)

    try:
        while True:
            # Keep connection alive, handle any spectator messages
            data = await websocket.receive_json()

            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "get_info":
                await websocket.send_json({
                    "type": "table_info",
                    "table_id": str(table_id),
                    "spectator_count": spectator_manager.get_spectator_count(table_id),
                    "delay_seconds": SPECTATOR_DELAY_SECONDS,
                })

            # Spectators can only observe, not interact with the game

    except WebSocketDisconnect:
        pass
    finally:
        await spectator_manager.disconnect(websocket, table_id)
