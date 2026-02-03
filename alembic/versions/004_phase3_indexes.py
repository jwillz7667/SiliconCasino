"""Phase 3 - Performance indexes and optimizations

Revision ID: 004
Revises: 003
Create Date: 2024-02-15 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Performance indexes for game_events
    op.create_index(
        "idx_game_events_hand_id",
        "game_events",
        ["hand_id"],
    )
    op.create_index(
        "idx_game_events_created_at",
        "game_events",
        ["created_at"],
    )
    op.create_index(
        "idx_game_events_agent_id",
        "game_events",
        ["agent_id"],
    )

    # Transaction query optimization
    op.create_index(
        "idx_transactions_wallet_id_created",
        "transactions",
        ["wallet_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "idx_transactions_type",
        "transactions",
        ["transaction_type"],
    )

    # Poker hand optimization
    op.create_index(
        "idx_poker_hands_table_status",
        "poker_hands",
        ["table_id", "status"],
    )
    op.create_index(
        "idx_poker_hands_created_at",
        "poker_hands",
        ["created_at"],
    )

    # Tournament entry optimization
    op.create_index(
        "idx_tournament_entries_tournament_status",
        "tournament_entries",
        ["tournament_id", "is_active"],
    )

    # Withdrawal request optimization
    op.create_index(
        "idx_withdrawal_requests_status_created",
        "withdrawal_requests",
        ["status", "created_at"],
    )

    # Partial indexes for common queries
    op.execute("""
        CREATE INDEX idx_active_tables
        ON poker_tables(id)
        WHERE status = 'active';
    """)

    op.execute("""
        CREATE INDEX idx_pending_withdrawals
        ON withdrawal_requests(id, created_at)
        WHERE status = 'pending';
    """)

    op.execute("""
        CREATE INDEX idx_active_tournaments
        ON tournaments(id)
        WHERE status IN ('registering', 'running');
    """)

    op.execute("""
        CREATE INDEX idx_active_agents
        ON agents(id)
        WHERE is_active = true;
    """)

    # Trivia optimization
    op.create_index(
        "idx_trivia_matches_status",
        "trivia_matches",
        ["status"],
    )
    op.create_index(
        "idx_trivia_participants_match",
        "trivia_participants",
        ["match_id", "is_active"],
    )

    # Prediction market optimization
    op.create_index(
        "idx_prediction_markets_status",
        "prediction_markets",
        ["status"],
    )
    op.create_index(
        "idx_prediction_positions_market_agent",
        "prediction_positions",
        ["market_id", "agent_id"],
    )


def downgrade() -> None:
    # Drop partial indexes
    op.execute("DROP INDEX IF EXISTS idx_active_tables;")
    op.execute("DROP INDEX IF EXISTS idx_pending_withdrawals;")
    op.execute("DROP INDEX IF EXISTS idx_active_tournaments;")
    op.execute("DROP INDEX IF EXISTS idx_active_agents;")

    # Drop regular indexes
    op.drop_index("idx_prediction_positions_market_agent", "prediction_positions")
    op.drop_index("idx_prediction_markets_status", "prediction_markets")
    op.drop_index("idx_trivia_participants_match", "trivia_participants")
    op.drop_index("idx_trivia_matches_status", "trivia_matches")
    op.drop_index("idx_withdrawal_requests_status_created", "withdrawal_requests")
    op.drop_index("idx_tournament_entries_tournament_status", "tournament_entries")
    op.drop_index("idx_poker_hands_created_at", "poker_hands")
    op.drop_index("idx_poker_hands_table_status", "poker_hands")
    op.drop_index("idx_transactions_type", "transactions")
    op.drop_index("idx_transactions_wallet_id_created", "transactions")
    op.drop_index("idx_game_events_agent_id", "game_events")
    op.drop_index("idx_game_events_created_at", "game_events")
    op.drop_index("idx_game_events_hand_id", "game_events")
