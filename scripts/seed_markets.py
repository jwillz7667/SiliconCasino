#!/usr/bin/env python3
"""
Seed sample prediction markets for testing.

Run with: python scripts/seed_markets.py
"""

from datetime import datetime, timedelta, timezone

from backend.game_engine.predictions import prediction_engine


def seed_markets():
    """Create sample prediction markets."""
    
    markets = [
        {
            "question": "Will Bitcoin exceed $100,000 by March 1, 2026?",
            "description": "Market resolves YES if BTC/USD price exceeds $100,000 at any point before March 1, 2026 00:00 UTC.",
            "category": "crypto",
            "resolution_time": datetime(2026, 3, 1, tzinfo=timezone.utc),
            "oracle_source": "coingecko",
            "oracle_data": {"asset": "bitcoin", "threshold": 100000},
        },
        {
            "question": "Will GPT-5 be released before June 2026?",
            "description": "Market resolves YES if OpenAI publicly releases GPT-5 (or equivalent next-gen model) before June 1, 2026.",
            "category": "technology",
            "resolution_time": datetime(2026, 6, 1, tzinfo=timezone.utc),
            "oracle_source": "manual",
            "oracle_data": {},
        },
        {
            "question": "Will Ethereum flip Bitcoin market cap in 2026?",
            "description": "Market resolves YES if ETH market cap exceeds BTC market cap at any point during 2026.",
            "category": "crypto",
            "resolution_time": datetime(2027, 1, 1, tzinfo=timezone.utc),
            "oracle_source": "coingecko",
            "oracle_data": {"comparison": "eth_vs_btc"},
        },
        {
            "question": "Will Silicon Casino have 1000+ registered agents by April 2026?",
            "description": "Meta-market! Resolves YES if Silicon Casino reaches 1000 registered agent accounts.",
            "category": "meta",
            "resolution_time": datetime(2026, 4, 1, tzinfo=timezone.utc),
            "oracle_source": "manual",
            "oracle_data": {},
        },
        {
            "question": "Will there be a US interest rate cut in Q1 2026?",
            "description": "Market resolves YES if the Federal Reserve cuts interest rates between Jan 1 and March 31, 2026.",
            "category": "finance",
            "resolution_time": datetime(2026, 4, 1, tzinfo=timezone.utc),
            "oracle_source": "manual",
            "oracle_data": {},
        },
    ]
    
    created = []
    for market_data in markets:
        market = prediction_engine.create_market(
            question=market_data["question"],
            description=market_data["description"],
            category=market_data["category"],
            resolution_time=market_data["resolution_time"],
            oracle_source=market_data["oracle_source"],
            oracle_data=market_data["oracle_data"],
            initial_liquidity=1000,
        )
        created.append(market)
        print(f"Created market: {market.question[:50]}...")
    
    print(f"\nCreated {len(created)} markets!")
    return created


if __name__ == "__main__":
    markets = seed_markets()
    
    print("\nMarket Summary:")
    print("-" * 60)
    for m in markets:
        print(f"  [{m.category}] {m.question[:45]}...")
        print(f"    YES: {float(m.yes_price):.2f} | NO: {float(m.no_price):.2f}")
        print()
