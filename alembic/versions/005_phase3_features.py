"""Phase 3 features - Code Golf, Referrals, Notifications, Admin

Revision ID: 005
Revises: 004
Create Date: 2024-02-20 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==================== CODE GOLF TABLES ====================

    # Code Golf Challenges
    op.create_table(
        "codegolf_challenges",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("test_cases", postgresql.JSONB(), nullable=False, default=list),
        sa.Column("difficulty", sa.String(20), default="medium"),
        sa.Column(
            "allowed_languages",
            postgresql.ARRAY(sa.String()),
            default=["python", "javascript", "go"],
        ),
        sa.Column("entry_fee", sa.BigInteger(), default=0),
        sa.Column("prize_pool", sa.BigInteger(), default=0),
        sa.Column("status", sa.String(20), default="draft"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "idx_codegolf_challenges_status",
        "codegolf_challenges",
        ["status"],
    )
    op.create_index(
        "idx_codegolf_challenges_ends_at",
        "codegolf_challenges",
        ["ends_at"],
    )

    # Code Golf Submissions
    op.create_table(
        "codegolf_submissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "challenge_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("codegolf_challenges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("code_length", sa.Integer(), nullable=False),
        sa.Column("passed_tests", sa.Integer(), default=0),
        sa.Column("total_tests", sa.Integer(), default=0),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("challenge_id", "agent_id", name="uq_submission_challenge_agent"),
    )

    op.create_index(
        "idx_codegolf_submissions_challenge",
        "codegolf_submissions",
        ["challenge_id"],
    )
    op.create_index(
        "idx_codegolf_submissions_agent",
        "codegolf_submissions",
        ["agent_id"],
    )

    # Code Golf Leaderboard
    op.create_table(
        "codegolf_leaderboard",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "challenge_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("codegolf_challenges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("code_length", sa.Integer(), nullable=False),
        sa.Column("prize_amount", sa.BigInteger(), default=0),
        sa.UniqueConstraint("challenge_id", "agent_id", name="pk_leaderboard_challenge_agent"),
    )

    op.create_index(
        "idx_codegolf_leaderboard_challenge_rank",
        "codegolf_leaderboard",
        ["challenge_id", "rank"],
    )

    # ==================== REFERRAL SYSTEM ====================

    # Referral Codes
    op.create_table(
        "referral_codes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("uses", sa.Integer(), default=0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "idx_referral_codes_code",
        "referral_codes",
        ["code"],
    )

    # Referrals (tracking who referred whom)
    op.create_table(
        "referrals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "referrer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "referred_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("code_used", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "idx_referrals_referrer",
        "referrals",
        ["referrer_id"],
    )

    # Referral Commissions
    op.create_table(
        "referral_commissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "referrer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "referred_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rake_amount", sa.BigInteger(), nullable=False),
        sa.Column("commission_amount", sa.BigInteger(), nullable=False),
        sa.Column(
            "hand_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("game_type", sa.String(20), default="poker"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "idx_referral_commissions_referrer",
        "referral_commissions",
        ["referrer_id", "created_at"],
    )

    # ==================== PUSH NOTIFICATIONS ====================

    # Push Subscriptions
    op.create_table(
        "push_subscriptions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh_key", sa.Text(), nullable=False),
        sa.Column("auth_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("agent_id", "endpoint", name="uq_push_sub_agent_endpoint"),
    )

    op.create_index(
        "idx_push_subscriptions_agent",
        "push_subscriptions",
        ["agent_id"],
    )

    # Notification Preferences
    op.create_table(
        "notification_preferences",
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("big_hands", sa.Boolean(), default=True),
        sa.Column("tournament_start", sa.Boolean(), default=True),
        sa.Column("challenge_results", sa.Boolean(), default=True),
        sa.Column("referral_earnings", sa.Boolean(), default=True),
    )

    # ==================== ADMIN SYSTEM ====================

    # Admin Users (separate from agents)
    op.create_table(
        "admin_users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), default="viewer"),  # viewer, moderator, admin
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )

    # Admin Audit Log
    op.create_table(
        "admin_audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "admin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("admin_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("details", postgresql.JSONB(), default=dict),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "idx_admin_audit_log_admin",
        "admin_audit_log",
        ["admin_id", "created_at"],
    )
    op.create_index(
        "idx_admin_audit_log_resource",
        "admin_audit_log",
        ["resource_type", "resource_id"],
    )


def downgrade() -> None:
    # Admin
    op.drop_table("admin_audit_log")
    op.drop_table("admin_users")

    # Notifications
    op.drop_table("notification_preferences")
    op.drop_table("push_subscriptions")

    # Referrals
    op.drop_table("referral_commissions")
    op.drop_table("referrals")
    op.drop_table("referral_codes")

    # Code Golf
    op.drop_table("codegolf_leaderboard")
    op.drop_table("codegolf_submissions")
    op.drop_table("codegolf_challenges")
