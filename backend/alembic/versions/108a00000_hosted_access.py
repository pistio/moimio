"""Persisted session rotation and private Hosted bootstrap binding."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "108a00000"
down_revision = "107a00000"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("refresh_digest", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_table(
        "hosted_bootstrap_grants",
        sa.Column("tenant_id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), unique=True, nullable=False),
        sa.Column("public_origin", sa.String(255), nullable=False),
        sa.Column("buyer_commitment", sa.String(64), nullable=False),
        sa.Column("transaction_commitment", sa.String(64), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    raise RuntimeError("HOSTED_ACCESS_UNSAFE_DOWNGRADE_REVIEW_REQUIRED")
