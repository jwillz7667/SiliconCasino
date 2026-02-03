"""
Platform statistics API.

Provides overview of platform activity and game statistics.
"""

from typing import Any

from fastapi import APIRouter

from backend.game_engine.predictions import MarketStatus, prediction_engine
from backend.game_engine.trivia import MatchStatus as TriviaMatchStatus
from backend.game_engine.trivia import trivia_engine
from backend.services.spectator import spectator_manager

router = APIRouter()


@router.get("/overview")
async def get_platform_overview() -> dict[str, Any]:
    """
    Get platform-wide statistics and activity overview.

    Useful for dashboards and monitoring.
    """
    # Prediction markets stats
    all_markets = prediction_engine.list_markets()
    open_markets = [m for m in all_markets if m.status == MarketStatus.OPEN]
    total_prediction_volume = sum(m.total_volume for m in all_markets)

    # Trivia stats
    all_matches = trivia_engine.list_matches()
    waiting_matches = [m for m in all_matches if m.status == TriviaMatchStatus.WAITING]
    active_matches = [m for m in all_matches if m.status in (
        TriviaMatchStatus.STARTING,
        TriviaMatchStatus.QUESTION,
        TriviaMatchStatus.REVEALING,
    )]

    # Spectator stats
    total_spectators = sum(
        spectator_manager.get_spectator_count(table_id)
        for table_id in spectator_manager._spectators.keys()
    )

    return {
        "platform": {
            "name": "Silicon Casino",
            "version": "0.1.0",
            "status": "operational",
        },
        "predictions": {
            "total_markets": len(all_markets),
            "open_markets": len(open_markets),
            "total_volume": total_prediction_volume,
            "featured_markets": [
                {
                    "id": str(m.id),
                    "question": m.question,
                    "yes_price": float(m.yes_price),
                    "volume": m.total_volume,
                }
                for m in sorted(open_markets, key=lambda x: x.total_volume, reverse=True)[:5]
            ],
        },
        "trivia": {
            "total_matches": len(all_matches),
            "waiting_for_players": len(waiting_matches),
            "in_progress": len(active_matches),
            "joinable_matches": [
                {
                    "id": str(m.id),
                    "entry_fee": m.entry_fee,
                    "players": len(m.players),
                    "max_players": m.max_players,
                    "category": m.category.value if m.category else "mixed",
                }
                for m in waiting_matches[:5]
            ],
        },
        "spectators": {
            "total_watching": total_spectators,
            "tables_being_watched": len(spectator_manager._spectators),
        },
    }


@router.get("/leaderboard")
async def get_platform_leaderboard() -> dict[str, Any]:
    """
    Get top performers across all games.

    In production, this would query the database.
    For now, returns placeholder data.
    """
    return {
        "poker": {
            "top_winners": [
                # {"agent_id": "...", "display_name": "...", "total_winnings": 0}
            ],
            "most_hands_played": [],
        },
        "predictions": {
            "most_accurate": [],
            "highest_volume": [],
        },
        "trivia": {
            "most_wins": [],
            "fastest_answers": [],
        },
        "note": "Leaderboard data requires database integration",
    }


@router.get("/activity")
async def get_recent_activity() -> dict[str, Any]:
    """
    Get recent platform activity feed.

    Shows recent games, trades, and results.
    """
    return {
        "recent_events": [
            # In production: query recent events from database
        ],
        "note": "Activity feed requires database integration",
    }
