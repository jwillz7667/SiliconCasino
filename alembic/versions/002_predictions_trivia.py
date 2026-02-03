"""Prediction markets and trivia tables

Revision ID: 002
Revises: 001
Create Date: 2024-01-15 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create market_status enum
    market_status = postgresql.ENUM(
        "OPEN", "CLOSED", "RESOLVED", "CANCELLED",
        name="market_status",
        create_type=False,
    )
    market_status.create(op.get_bind(), checkfirst=True)

    # Prediction markets table
    op.create_table(
        "prediction_markets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("question", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), default=""),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column(
            "status",
            sa.Enum("OPEN", "CLOSED", "RESOLVED", "CANCELLED", name="market_status"),
            default="OPEN",
        ),
        sa.Column("resolution_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("oracle_source", sa.String(50), default="manual"),
        sa.Column("oracle_data", postgresql.JSONB(), default={}),
        sa.Column("yes_pool", sa.Integer(), default=1000),
        sa.Column("no_pool", sa.Integer(), default=1000),
        sa.Column("total_volume", sa.Integer(), default=0),
        sa.Column("resolved_outcome", sa.String(10), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_prediction_markets_category", "prediction_markets", ["category"])
    op.create_index("ix_prediction_markets_status", "prediction_markets", ["status"])

    # Prediction positions table
    op.create_table(
        "prediction_positions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "market_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prediction_markets.id"),
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
        ),
        sa.Column("outcome", sa.String(10), nullable=False),
        sa.Column("shares", sa.Integer(), default=0),
        sa.Column("avg_price", sa.Numeric(10, 4), default=0),
        sa.Column("cost_basis", sa.Integer(), default=0),
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
    op.create_index("ix_prediction_positions_market_id", "prediction_positions", ["market_id"])
    op.create_index("ix_prediction_positions_agent_id", "prediction_positions", ["agent_id"])

    # Prediction trades table
    op.create_table(
        "prediction_trades",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "market_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prediction_markets.id"),
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
        ),
        sa.Column("trade_type", sa.String(10), nullable=False),
        sa.Column("outcome", sa.String(10), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("yes_price_before", sa.Numeric(10, 4)),
        sa.Column("yes_price_after", sa.Numeric(10, 4)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_prediction_trades_market_id", "prediction_trades", ["market_id"])
    op.create_index("ix_prediction_trades_agent_id", "prediction_trades", ["agent_id"])
    op.create_index("ix_prediction_trades_created_at", "prediction_trades", ["created_at"])

    # Create trivia_status enum
    trivia_status = postgresql.ENUM(
        "WAITING", "STARTING", "QUESTION", "REVEALING", "COMPLETE",
        name="trivia_status",
        create_type=False,
    )
    trivia_status.create(op.get_bind(), checkfirst=True)

    # Trivia questions table
    op.create_table(
        "trivia_questions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("correct_answer", sa.String(500), nullable=False),
        sa.Column("incorrect_answers", postgresql.ARRAY(sa.String(500)), nullable=False),
        sa.Column("difficulty", sa.Integer(), default=1),
        sa.Column("time_limit_seconds", sa.Integer(), default=15),
        sa.Column("times_used", sa.Integer(), default=0),
        sa.Column("times_correct", sa.Integer(), default=0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_trivia_questions_category", "trivia_questions", ["category"])

    # Trivia matches table
    op.create_table(
        "trivia_matches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "status",
            sa.Enum("WAITING", "STARTING", "QUESTION", "REVEALING", "COMPLETE", name="trivia_status"),
            default="WAITING",
        ),
        sa.Column("entry_fee", sa.Integer(), nullable=False),
        sa.Column("max_players", sa.Integer(), default=8),
        sa.Column("questions_count", sa.Integer(), default=10),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("prize_pool", sa.Integer(), default=0),
        sa.Column(
            "winner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=True,
        ),
        sa.Column("current_question_index", sa.Integer(), default=0),
        sa.Column("question_ids", postgresql.ARRAY(sa.String(36)), default=[]),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_trivia_matches_status", "trivia_matches", ["status"])

    # Trivia participants table
    op.create_table(
        "trivia_participants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "match_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trivia_matches.id"),
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
        ),
        sa.Column("score", sa.Integer(), default=0),
        sa.Column("answers_correct", sa.Integer(), default=0),
        sa.Column("answers_wrong", sa.Integer(), default=0),
        sa.Column("fastest_answer_ms", sa.Integer(), nullable=True),
        sa.Column("payout", sa.Integer(), default=0),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_trivia_participants_match_id", "trivia_participants", ["match_id"])
    op.create_index("ix_trivia_participants_agent_id", "trivia_participants", ["agent_id"])

    # Trivia answers table
    op.create_table(
        "trivia_answers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "match_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trivia_matches.id"),
        ),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trivia_questions.id"),
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
        ),
        sa.Column("answer", sa.String(500), nullable=False),
        sa.Column("is_correct", sa.Boolean(), default=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=False),
        sa.Column("points_earned", sa.Integer(), default=0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_trivia_answers_match_id", "trivia_answers", ["match_id"])
    op.create_index("ix_trivia_answers_question_id", "trivia_answers", ["question_id"])
    op.create_index("ix_trivia_answers_agent_id", "trivia_answers", ["agent_id"])


def downgrade() -> None:
    op.drop_table("trivia_answers")
    op.drop_table("trivia_participants")
    op.drop_table("trivia_matches")
    op.drop_table("trivia_questions")
    op.drop_table("prediction_trades")
    op.drop_table("prediction_positions")
    op.drop_table("prediction_markets")

    op.execute("DROP TYPE IF EXISTS market_status")
    op.execute("DROP TYPE IF EXISTS trivia_status")
