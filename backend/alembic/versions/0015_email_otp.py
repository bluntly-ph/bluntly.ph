"""email_otps — one-time codes for passwordless auth (Slice 1 Phase A)

The partial index on (email, purpose) WHERE consumed_at IS NULL supports the
hot path: "find this address's live code". Requesting a new code consumes any
outstanding one, so at most a handful of rows ever match.

Codes are stored as Argon2id hashes, never plaintext. `attempts` is the
authoritative verify limit — the Redis limiter fails open by design, so the cap
has to live in Postgres or a Redis outage would allow unlimited guesses.

Revision ID: 0015_email_otp
Revises: 0014_schema_parity
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015_email_otp"
down_revision = "0014_schema_parity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    otp_purpose = postgresql.ENUM("signup", "login", name="otp_purpose",
                                  create_type=False)
    otp_purpose.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "email_otps",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("purpose", otp_purpose, nullable=False),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_email_otps_email", "email_otps", ["email"])
    op.execute("CREATE INDEX ix_email_otps_live ON email_otps (email, purpose) "
               "WHERE consumed_at IS NULL")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_email_otps_live")
    op.drop_index("ix_email_otps_email", table_name="email_otps")
    op.drop_table("email_otps")
    op.execute("DROP TYPE IF EXISTS otp_purpose")
