"""Phase 2 features - Tournaments, Withdrawals, Crypto

Revision ID: 003
Revises: 002
Create Date: 2024-02-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add trust_level to agents table
    op.add_column(
        "agents",
        sa.Column("trust_level", sa.Float(), nullable=False, server_default="1.0"),
    )

    # Tournaments table
    op.create_table(
        "tournaments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("format", sa.String(20), default="freezeout"),
        sa.Column("buy_in", sa.BigInteger(), nullable=False),
        sa.Column("rake", sa.BigInteger(), default=0),
        sa.Column("starting_chips", sa.BigInteger(), default=10000),
        sa.Column("min_players", sa.Integer(), default=2),
        sa.Column("max_players", sa.Integer(), default=100),
        sa.Column("blind_structure", postgresql.JSONB(), default=list),
        sa.Column("level_duration_minutes", sa.Integer(), default=15),
        sa.Column("current_level", sa.Integer(), default=0),
        sa.Column("prize_structure", postgresql.JSONB(), default=dict),
        sa.Column("status", sa.String(20), default="registering"),
        sa.Column("registration_opens_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_prize_pool", sa.BigInteger(), default=0),
        sa.Column("entries_count", sa.Integer(), default=0),
        sa.Column("rebuys_count", sa.Integer(), default=0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )

    # Tournament entries table
    op.create_table(
        "tournament_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tournament_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tournaments.id"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("is_eliminated", sa.Boolean(), default=False),
        sa.Column("finish_position", sa.Integer(), nullable=True),
        sa.Column("current_chips", sa.BigInteger(), default=0),
        sa.Column("rebuys", sa.Integer(), default=0),
        sa.Column("total_invested", sa.BigInteger(), default=0),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.Column("eliminated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "table_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("poker_tables.id"),
            nullable=True,
        ),
        sa.Column("seat_number", sa.Integer(), nullable=True),
    )
    op.create_index("ix_tournament_entries_tournament_id", "tournament_entries", ["tournament_id"])
    op.create_index("ix_tournament_entries_agent_id", "tournament_entries", ["agent_id"])

    # Tournament payouts table
    op.create_table(
        "tournament_payouts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tournament_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tournaments.id"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=False,
        ),
        sa.Column("finish_position", sa.Integer(), nullable=False),
        sa.Column("prize_amount", sa.BigInteger(), nullable=False),
        sa.Column("is_paid", sa.Boolean(), default=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_tournament_payouts_tournament_id", "tournament_payouts", ["tournament_id"])
    op.create_index("ix_tournament_payouts_agent_id", "tournament_payouts", ["agent_id"])

    # Withdrawal requests table
    op.create_table(
        "withdrawal_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=False,
        ),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("destination_address", sa.String(255), nullable=False),
        sa.Column("chain", sa.String(50), default="polygon"),
        sa.Column("token", sa.String(20), default="USDC"),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("tx_hash", sa.String(100), nullable=True),
        sa.Column("tx_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_withdrawal_requests_agent_id", "withdrawal_requests", ["agent_id"])

    # Deposit addresses table
    op.create_table(
        "deposit_addresses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("address", sa.String(255), nullable=False, unique=True),
        sa.Column("chain", sa.String(50), default="polygon"),
        sa.Column("derivation_index", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )

    # Crypto deposits table
    op.create_table(
        "crypto_deposits",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=False,
        ),
        sa.Column("tx_hash", sa.String(100), nullable=False, unique=True),
        sa.Column("from_address", sa.String(255), nullable=False),
        sa.Column("to_address", sa.String(255), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("token", sa.String(20), default="USDC"),
        sa.Column("chain", sa.String(50), default="polygon"),
        sa.Column("block_number", sa.BigInteger(), nullable=False),
        sa.Column("confirmations", sa.BigInteger(), default=0),
        sa.Column("is_credited", sa.Boolean(), default=False),
        sa.Column("credited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_crypto_deposits_agent_id", "crypto_deposits", ["agent_id"])


def downgrade() -> None:
    op.drop_table("crypto_deposits")
    op.drop_table("deposit_addresses")
    op.drop_table("withdrawal_requests")
    op.drop_table("tournament_payouts")
    op.drop_table("tournament_entries")
    op.drop_table("tournaments")
    op.drop_column("agents", "trust_level")
