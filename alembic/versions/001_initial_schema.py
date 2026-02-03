"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agents table
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("moltbook_id", sa.String(255), unique=True, nullable=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("api_key_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_agents_moltbook_id", "agents", ["moltbook_id"])

    # Wallets table
    op.create_table(
        "wallets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), unique=True),
        sa.Column("balance", sa.BigInteger(), default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # Transactions table
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("wallet_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wallets.id")),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_transactions_wallet_id", "transactions", ["wallet_id"])
    op.create_index("ix_transactions_created_at", "transactions", ["created_at"])

    # Poker tables
    op.create_table(
        "poker_tables",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("small_blind", sa.BigInteger(), nullable=False),
        sa.Column("big_blind", sa.BigInteger(), nullable=False),
        sa.Column("min_buy_in", sa.BigInteger(), nullable=False),
        sa.Column("max_buy_in", sa.BigInteger(), nullable=False),
        sa.Column("max_players", sa.SmallInteger(), default=6),
        sa.Column("status", sa.String(20), default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # Table seats
    op.create_table(
        "table_seats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("poker_tables.id")),
        sa.Column("seat_number", sa.SmallInteger(), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("stack", sa.BigInteger(), default=0),
        sa.Column("status", sa.String(20), default="empty"),
        sa.UniqueConstraint("table_id", "seat_number", name="uq_table_seat"),
    )
    op.create_index("ix_table_seats_table_id", "table_seats", ["table_id"])

    # Poker hands
    op.create_table(
        "poker_hands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("poker_tables.id")),
        sa.Column("hand_number", sa.BigInteger(), nullable=False),
        sa.Column("button_seat", sa.SmallInteger(), nullable=False),
        sa.Column("community_cards", sa.String(20), nullable=True),
        sa.Column("total_pot", sa.BigInteger(), default=0),
        sa.Column("status", sa.String(20), default="in_progress"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_poker_hands_table_id", "poker_hands", ["table_id"])

    # Game events
    op.create_table(
        "game_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("hand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("poker_hands.id")),
        sa.Column("sequence_num", sa.SmallInteger(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_game_events_hand_id", "game_events", ["hand_id"])


def downgrade() -> None:
    op.drop_table("game_events")
    op.drop_table("poker_hands")
    op.drop_table("table_seats")
    op.drop_table("poker_tables")
    op.drop_table("transactions")
    op.drop_table("wallets")
    op.drop_table("agents")
