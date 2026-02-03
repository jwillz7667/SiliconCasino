import asyncio
import json
from typing import Any, Callable

import websockets
from websockets.client import WebSocketClientProtocol


class WebSocketClient:
    """WebSocket client for real-time game updates."""

    def __init__(
        self,
        url: str,
        on_message: Callable[[dict[str, Any]], None] | None = None,
    ):
        self.url = url
        self._on_message = on_message
        self._ws: WebSocketClientProtocol | None = None
        self._receive_task: asyncio.Task | None = None
        self._message_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._connected = asyncio.Event()

    async def connect(self) -> None:
        """Establish WebSocket connection."""
        self._ws = await websockets.connect(self.url)
        self._connected.set()
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        self._connected.clear()
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def send(self, message: dict[str, Any]) -> None:
        """Send a message."""
        if not self._ws:
            raise RuntimeError("Not connected")
        await self._ws.send(json.dumps(message))

    async def receive(self, timeout: float | None = None) -> dict[str, Any]:
        """Receive the next message from the queue."""
        try:
            return await asyncio.wait_for(self._message_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError("No message received within timeout")

    async def _receive_loop(self) -> None:
        """Background task to receive messages."""
        if not self._ws:
            return

        try:
            async for raw_message in self._ws:
                try:
                    message = json.loads(raw_message)
                    await self._message_queue.put(message)
                    if self._on_message:
                        self._on_message(message)
                except json.JSONDecodeError:
                    continue
        except websockets.ConnectionClosed:
            pass
        finally:
            self._connected.clear()

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._ws is not None and self._connected.is_set()

    async def wait_for_message(
        self,
        message_type: str,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        """Wait for a specific message type."""
        deadline = asyncio.get_event_loop().time() + timeout

        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError(f"Timeout waiting for {message_type}")

            message = await self.receive(timeout=remaining)
            if message.get("type") == message_type:
                return message

    async def ping(self) -> bool:
        """Send a ping and wait for pong."""
        await self.send({"type": "ping"})
        try:
            response = await self.wait_for_message("pong", timeout=5.0)
            return response.get("type") == "pong"
        except TimeoutError:
            return False
