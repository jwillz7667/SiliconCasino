#!/usr/bin/env python3
"""Load testing suite for Silicon Casino using Locust.

Run with: locust -f scripts/load_test.py --host=http://localhost:8000 --headless -u 100 -r 10 -t 5m

Targets:
- 100 concurrent WebSocket connections
- 1000 actions/minute sustained
- p99 latency < 200ms
- Zero dropped connections
"""

import json
import random
import time
from typing import Optional
from uuid import uuid4

from locust import HttpUser, between, task, events
from locust.clients import HttpSession
import websocket


# Test configuration
class TestConfig:
    NUM_TABLES = 5
    SMALL_BLIND = 10
    BIG_BLIND = 20
    MIN_BUY_IN = 1000
    MAX_BUY_IN = 10000


# Track created resources for cleanup
created_agents: list[dict] = []
created_tables: list[str] = []


class PokerAgentUser(HttpUser):
    """Simulates an AI agent interacting with the poker platform."""

    wait_time = between(0.5, 2.0)  # Wait between 0.5-2 seconds between tasks
    abstract = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent_id: Optional[str] = None
        self.token: Optional[str] = None
        self.current_table: Optional[str] = None
        self.ws: Optional[websocket.WebSocket] = None

    def on_start(self) -> None:
        """Register and authenticate agent on start."""
        self.register_agent()

    def on_stop(self) -> None:
        """Cleanup on stop."""
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass

    def register_agent(self) -> None:
        """Register a new test agent."""
        display_name = f"LoadTest_{uuid4().hex[:8]}"

        with self.client.post(
            "/api/auth/register",
            json={"display_name": display_name},
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                data = response.json()
                self.agent_id = data["agent_id"]
                self.token = data["access_token"]
                created_agents.append({"id": self.agent_id, "token": self.token})
                response.success()
            else:
                response.failure(f"Registration failed: {response.text}")

    @property
    def auth_headers(self) -> dict:
        """Get authorization headers."""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @task(10)
    def get_lobby(self) -> None:
        """Get lobby information - most common read operation."""
        self.client.get(
            "/api/poker/tables",
            headers=self.auth_headers,
            name="/api/poker/tables",
        )

    @task(5)
    def get_balance(self) -> None:
        """Check wallet balance."""
        if not self.agent_id:
            return
        self.client.get(
            "/api/wallet/balance",
            headers=self.auth_headers,
            name="/api/wallet/balance",
        )

    @task(3)
    def join_table(self) -> None:
        """Join a poker table."""
        if not self.token:
            return

        # Get available tables
        with self.client.get(
            "/api/poker/tables",
            headers=self.auth_headers,
            catch_response=True,
            name="/api/poker/tables",
        ) as response:
            if response.status_code != 200:
                return
            tables = response.json()
            if not tables:
                return
            response.success()

        # Find a table with available seats
        available_tables = [
            t for t in tables
            if t.get("player_count", 0) < t.get("max_players", 9)
        ]
        if not available_tables:
            return

        table = random.choice(available_tables)
        table_id = table["id"]

        # Find an empty seat
        with self.client.get(
            f"/api/poker/tables/{table_id}",
            headers=self.auth_headers,
            catch_response=True,
            name="/api/poker/tables/{id}",
        ) as response:
            if response.status_code != 200:
                return
            table_data = response.json()
            response.success()

        seats = table_data.get("seats", [])
        empty_seats = [s["number"] for s in seats if s.get("agent_id") is None]
        if not empty_seats:
            return

        seat_number = random.choice(empty_seats)
        buy_in = random.randint(TestConfig.MIN_BUY_IN, TestConfig.MAX_BUY_IN)

        with self.client.post(
            f"/api/poker/tables/{table_id}/join",
            headers=self.auth_headers,
            json={"seat_number": seat_number, "buy_in": buy_in},
            catch_response=True,
            name="/api/poker/tables/{id}/join",
        ) as response:
            if response.status_code in (200, 201):
                self.current_table = table_id
                response.success()
            elif response.status_code == 400:
                # Already seated or other validation error - not a failure
                response.success()
            else:
                response.failure(f"Join failed: {response.text}")

    @task(5)
    def take_action(self) -> None:
        """Take a poker action if at a table."""
        if not self.current_table or not self.token:
            return

        # Get current table state
        with self.client.get(
            f"/api/poker/tables/{self.current_table}",
            headers=self.auth_headers,
            catch_response=True,
            name="/api/poker/tables/{id}",
        ) as response:
            if response.status_code != 200:
                self.current_table = None
                return
            table_data = response.json()
            response.success()

        # Check if it's our turn
        current_player = table_data.get("current_player")
        if current_player != self.agent_id:
            return

        # Choose a random valid action
        actions = ["fold", "check", "call", "bet", "raise"]
        action = random.choice(actions)

        payload: dict = {"action": action}
        if action in ("bet", "raise"):
            payload["amount"] = random.randint(
                TestConfig.BIG_BLIND,
                TestConfig.BIG_BLIND * 10,
            )

        with self.client.post(
            f"/api/poker/tables/{self.current_table}/action",
            headers=self.auth_headers,
            json=payload,
            catch_response=True,
            name="/api/poker/tables/{id}/action",
        ) as response:
            if response.status_code in (200, 201):
                response.success()
            elif response.status_code == 400:
                # Invalid action (not our turn, etc.) - expected
                response.success()
            else:
                response.failure(f"Action failed: {response.text}")

    @task(2)
    def leave_table(self) -> None:
        """Leave current table."""
        if not self.current_table or not self.token:
            return

        with self.client.post(
            f"/api/poker/tables/{self.current_table}/leave",
            headers=self.auth_headers,
            catch_response=True,
            name="/api/poker/tables/{id}/leave",
        ) as response:
            self.current_table = None
            if response.status_code in (200, 204):
                response.success()
            elif response.status_code == 400:
                # Not at table - expected
                response.success()
            else:
                response.failure(f"Leave failed: {response.text}")

    @task(1)
    def get_hand_history(self) -> None:
        """Get hand history."""
        if not self.token:
            return
        self.client.get(
            "/api/poker/hands",
            headers=self.auth_headers,
            name="/api/poker/hands",
        )

    @task(1)
    def get_stats(self) -> None:
        """Get player statistics."""
        if not self.agent_id or not self.token:
            return
        self.client.get(
            f"/api/stats/{self.agent_id}",
            headers=self.auth_headers,
            name="/api/stats/{id}",
        )


class SpectatorUser(HttpUser):
    """Simulates a spectator watching games."""

    wait_time = between(1, 5)
    weight = 2  # Less common than poker agents

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.watching_table: Optional[str] = None

    @task(5)
    def browse_tables(self) -> None:
        """Browse available tables to watch."""
        self.client.get("/api/spectator/tables", name="/api/spectator/tables")

    @task(3)
    def watch_table(self) -> None:
        """Start watching a table."""
        with self.client.get(
            "/api/spectator/tables",
            catch_response=True,
            name="/api/spectator/tables",
        ) as response:
            if response.status_code != 200:
                return
            tables = response.json()
            if not tables:
                return
            response.success()

        # Pick a random table to watch
        table = random.choice(tables)
        self.watching_table = table.get("id")

        self.client.get(
            f"/api/spectator/tables/{self.watching_table}",
            name="/api/spectator/tables/{id}",
        )

    @task(2)
    def get_delayed_state(self) -> None:
        """Get delayed game state for spectator."""
        if not self.watching_table:
            return
        self.client.get(
            f"/api/spectator/tables/{self.watching_table}/state",
            name="/api/spectator/tables/{id}/state",
        )


class AdminUser(HttpUser):
    """Simulates admin operations."""

    wait_time = between(5, 15)
    weight = 1  # Rare compared to regular users

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token: Optional[str] = None

    @task(1)
    def health_check(self) -> None:
        """Check system health."""
        self.client.get("/health", name="/health")

    @task(1)
    def get_system_info(self) -> None:
        """Get system information."""
        self.client.get("/", name="/")


# WebSocket load test (separate from Locust)
class WebSocketLoadTest:
    """Standalone WebSocket load tester."""

    def __init__(self, base_url: str, num_connections: int = 100):
        self.base_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        self.num_connections = num_connections
        self.connections: list[websocket.WebSocket] = []
        self.messages_received = 0
        self.errors = 0

    def connect(self, token: str) -> Optional[websocket.WebSocket]:
        """Create a WebSocket connection."""
        try:
            ws = websocket.create_connection(
                f"{self.base_url}/api/ws",
                header={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            return ws
        except Exception as e:
            self.errors += 1
            print(f"WebSocket connection error: {e}")
            return None

    def run_test(self, duration_seconds: int = 60) -> dict:
        """Run WebSocket load test.

        Creates connections and monitors them for the specified duration.
        """
        print(f"Starting WebSocket load test with {self.num_connections} connections...")

        # Create connections
        for agent in created_agents[:self.num_connections]:
            ws = self.connect(agent["token"])
            if ws:
                self.connections.append(ws)

        print(f"Established {len(self.connections)} connections")

        # Monitor for duration
        start_time = time.time()
        while time.time() - start_time < duration_seconds:
            for ws in self.connections:
                try:
                    ws.settimeout(0.1)
                    msg = ws.recv()
                    if msg:
                        self.messages_received += 1
                except websocket.WebSocketTimeoutException:
                    pass
                except Exception as e:
                    self.errors += 1

            time.sleep(0.1)

        # Cleanup
        for ws in self.connections:
            try:
                ws.close()
            except Exception:
                pass

        return {
            "connections": len(self.connections),
            "messages_received": self.messages_received,
            "errors": self.errors,
            "duration_seconds": duration_seconds,
        }


# Event hooks for metrics
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, **kwargs):
    """Track request metrics."""
    # Log slow requests
    if response_time > 200:
        print(f"Slow request: {name} took {response_time:.0f}ms")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Cleanup after test."""
    print(f"\nTest completed. Created {len(created_agents)} test agents.")


if __name__ == "__main__":
    import subprocess
    import sys

    # Run Locust with default settings
    subprocess.run([
        sys.executable, "-m", "locust",
        "-f", __file__,
        "--host", "http://localhost:8000",
        "--headless",
        "-u", "100",
        "-r", "10",
        "-t", "5m",
        "--html", "load_test_report.html",
    ])
