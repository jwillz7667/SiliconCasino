"""
Spectator streaming service.

Handles delayed streaming of game events to spectators,
preventing information leakage while enabling live viewing.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

from fastapi import WebSocket


# Delay in seconds before events are visible to spectators
SPECTATOR_DELAY_SECONDS = 30


@dataclass
class DelayedEvent:
    """An event waiting to be broadcast to spectators."""
    
    event_type: str
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def is_ready(self) -> bool:
        """Check if event is past the delay threshold."""
        elapsed = (datetime.now(timezone.utc) - self.timestamp).total_seconds()
        return elapsed >= SPECTATOR_DELAY_SECONDS
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.event_type,
            "data": self.payload,
            "timestamp": self.timestamp.isoformat(),
        }


class SpectatorManager:
    """
    Manages spectator WebSocket connections and delayed event broadcasting.
    """
    
    def __init__(self):
        # table_id -> list of spectator websockets
        self._spectators: dict[UUID, list[WebSocket]] = defaultdict(list)
        
        # table_id -> list of delayed events
        self._event_queues: dict[UUID, list[DelayedEvent]] = defaultdict(list)
        
        # Background task for processing delayed events
        self._processor_task: asyncio.Task | None = None
        self._running = False
    
    async def start(self) -> None:
        """Start the background event processor."""
        if self._running:
            return
        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
    
    async def stop(self) -> None:
        """Stop the background event processor."""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
    
    async def connect(self, websocket: WebSocket, table_id: UUID) -> None:
        """Add a spectator to a table."""
        await websocket.accept()
        self._spectators[table_id].append(websocket)
        
        # Send welcome message
        await websocket.send_json({
            "type": "spectator_connected",
            "table_id": str(table_id),
            "delay_seconds": SPECTATOR_DELAY_SECONDS,
            "message": f"Connected as spectator. Events are delayed by {SPECTATOR_DELAY_SECONDS} seconds.",
        })
    
    async def disconnect(self, websocket: WebSocket, table_id: UUID) -> None:
        """Remove a spectator from a table."""
        if websocket in self._spectators[table_id]:
            self._spectators[table_id].remove(websocket)
        
        # Clean up empty lists
        if not self._spectators[table_id]:
            del self._spectators[table_id]
    
    def get_spectator_count(self, table_id: UUID) -> int:
        """Get number of spectators watching a table."""
        return len(self._spectators.get(table_id, []))
    
    async def queue_event(
        self,
        table_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """
        Queue an event for delayed broadcast to spectators.
        
        Events are held for SPECTATOR_DELAY_SECONDS before being
        sent to prevent information leakage (e.g., seeing hole cards).
        """
        # Sanitize payload - remove any private info
        sanitized = self._sanitize_for_spectators(event_type, payload)
        
        event = DelayedEvent(
            event_type=event_type,
            payload=sanitized,
        )
        self._event_queues[table_id].append(event)
    
    def _sanitize_for_spectators(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Remove private information from events before broadcasting.
        
        Spectators should never see:
        - Hole cards (until showdown)
        - Agent internal state
        - Private messages
        """
        sanitized = payload.copy()
        
        # Remove hole cards except at showdown
        if event_type != "showdown" and "your_cards" in sanitized:
            del sanitized["your_cards"]
        
        if event_type != "showdown" and "hole_cards" in sanitized:
            del sanitized["hole_cards"]
        
        # Remove agent-specific state
        if "valid_actions" in sanitized:
            del sanitized["valid_actions"]
        
        if "is_your_turn" in sanitized:
            del sanitized["is_your_turn"]
        
        return sanitized
    
    async def _process_events(self) -> None:
        """Background task that broadcasts delayed events."""
        while self._running:
            try:
                for table_id in list(self._event_queues.keys()):
                    queue = self._event_queues[table_id]
                    
                    # Find events ready to broadcast
                    ready_events = [e for e in queue if e.is_ready()]
                    
                    # Remove ready events from queue
                    self._event_queues[table_id] = [e for e in queue if not e.is_ready()]
                    
                    # Broadcast to spectators
                    for event in ready_events:
                        await self._broadcast_to_spectators(table_id, event)
                    
                    # Clean up empty queues
                    if not self._event_queues[table_id]:
                        del self._event_queues[table_id]
                
                # Check every second
                await asyncio.sleep(1.0)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                # Log error but keep running
                print(f"Spectator processor error: {e}")
                await asyncio.sleep(1.0)
    
    async def _broadcast_to_spectators(
        self,
        table_id: UUID,
        event: DelayedEvent,
    ) -> None:
        """Send an event to all spectators of a table."""
        spectators = self._spectators.get(table_id, [])
        
        if not spectators:
            return
        
        message = event.to_dict()
        
        # Send to all, removing disconnected
        disconnected = []
        for ws in spectators:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        
        # Clean up disconnected
        for ws in disconnected:
            await self.disconnect(ws, table_id)
    
    async def send_immediate(
        self,
        table_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """
        Send an event immediately (no delay).
        
        Use sparingly - only for non-sensitive info like:
        - Table status changes
        - Player join/leave (not cards)
        - Hand completion summary
        """
        sanitized = self._sanitize_for_spectators(event_type, payload)
        
        message = {
            "type": event_type,
            "data": sanitized,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        spectators = self._spectators.get(table_id, [])
        disconnected = []
        
        for ws in spectators:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        
        for ws in disconnected:
            await self.disconnect(ws, table_id)


# Global spectator manager
spectator_manager = SpectatorManager()
