#!/usr/bin/env python3
"""
Run multiple bot agents playing poker for testing.

Usage:
    python scripts/run_bots.py --hands 100
"""

import argparse
import asyncio
import random
from uuid import UUID

from silicon_casino import SiliconCasinoClient
from silicon_casino.poker import PokerClient


async def run_bot(
    name: str,
    table_id: str,
    seat: int,
    buy_in: int,
    base_url: str,
) -> None:
    """Run a single bot that plays random valid actions."""
    client = SiliconCasinoClient(base_url=base_url)

    try:
        await client.register(name)
        await client.authenticate()
        print(f"[{name}] Registered and authenticated")

        poker = PokerClient(base_url=base_url, token=client.token)

        await poker.join_table(table_id, seat, buy_in)
        print(f"[{name}] Joined table at seat {seat}")

        while True:
            await asyncio.sleep(0.5)

            try:
                state = await poker.get_table(table_id)
            except Exception as e:
                print(f"[{name}] Error getting state: {e}")
                continue

            if not state.get("is_your_turn"):
                continue

            valid_actions = state.get("valid_actions", [])
            if not valid_actions:
                continue

            weights = {
                "FOLD": 1,
                "CHECK": 10,
                "CALL": 8,
                "BET": 3,
                "RAISE": 2,
                "ALL_IN": 1,
            }

            weighted_actions = []
            for action in valid_actions:
                weight = weights.get(action, 1)
                weighted_actions.extend([action] * weight)

            action = random.choice(weighted_actions)

            hand = state.get("hand", {})
            min_raise = hand.get("min_raise_to", 20)
            current_bet = hand.get("current_bet", 0)

            amount = 0
            if action in ("BET", "RAISE"):
                max_bet = min_raise * 3
                amount = random.randint(min_raise, max(min_raise, max_bet))

            try:
                await poker.action(table_id, action.lower(), amount)
                print(f"[{name}] {action} {amount if amount else ''}")
            except Exception as e:
                print(f"[{name}] Action failed: {e}")

    except Exception as e:
        print(f"[{name}] Bot error: {e}")
    finally:
        await client.close()
        await poker.close()


async def run_game(
    num_bots: int = 2,
    num_hands: int = 100,
    base_url: str = "http://localhost:8000",
) -> None:
    """Run a game with multiple bots."""
    admin = SiliconCasinoClient(base_url=base_url)

    try:
        await admin.register("GameAdmin")
        await admin.authenticate()
        print("Admin registered")

        poker = PokerClient(base_url=base_url, token=admin.token)

        table = await poker.create_table(
            name=f"Bot Test Table",
            small_blind=5,
            big_blind=10,
            min_buy_in=100,
            max_buy_in=1000,
            max_players=6,
        )
        table_id = table["id"]
        print(f"Created table: {table_id}")

        tasks = []
        for i in range(num_bots):
            bot_task = asyncio.create_task(
                run_bot(
                    name=f"Bot_{i+1}",
                    table_id=table_id,
                    seat=i,
                    buy_in=500,
                    base_url=base_url,
                )
            )
            tasks.append(bot_task)

        print(f"Started {num_bots} bots, running for {num_hands} hands...")

        await asyncio.sleep(num_hands * 2)

        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        print("Test complete!")

    finally:
        await admin.close()


def main():
    parser = argparse.ArgumentParser(description="Run poker bots for testing")
    parser.add_argument("--bots", type=int, default=2, help="Number of bots")
    parser.add_argument("--hands", type=int, default=100, help="Number of hands to play")
    parser.add_argument("--url", type=str, default="http://localhost:8000", help="API URL")
    args = parser.parse_args()

    asyncio.run(run_game(args.bots, args.hands, args.url))


if __name__ == "__main__":
    main()
